# -*- coding: utf-8 -*-
"""
Created on Mon May  8 15:32:54 2023

@author: kernke
"""
import numpy as np
import matplotlib.pyplot as plt
import cv2
import imageio
import copy
from matplotlib.widgets import TextBox
import math
from .general_util import point_in_convex_ccw_roi,lineIntersection,assure_multiple
from .image_aligning import align_images
import json
import warnings

#%% make_scale_bar
def vis_make_scale_bar(
    images, pixratios, lengthperpix, barlength, org, thickness=4, color=(255, 0, 0)
):

    org = np.array(org)
    for i in range(len(images)):
        pixlength = (barlength / lengthperpix) / pixratios[i]
        pixlength = np.round(pixlength).astype(int)
        pt2 = org + np.array([0, pixlength])
        cv2.line(images[i], org[::-1], pt2[::-1], color, thickness=thickness)



#%% make_mp4
def vis_make_mp4(filename, images, fps):

    with imageio.get_writer(filename, mode="I", fps=fps) as writer:
        for i in range(len(images)):
            writer.append_data(images[i])

    return True


#%% zoom


def vis_zoom(img, zoom_center, final_height, steps, gif_resolution_to_final=1):

    iratio = img.shape[0] / img.shape[1]

    final_size = np.array([final_height, final_height / iratio])

    startpoints = np.zeros([4, 2], dtype=int)
    endpoints = np.zeros([4, 2], dtype=int)

    startpoints[2, 1] = img.shape[1] - 1
    startpoints[1, 0] = img.shape[0] - 1
    startpoints[3] = img.shape
    startpoints[3] -= 1

    endpoints[0] = np.round(zoom_center - final_size / 2).astype(int)
    endpoints[3] = np.round(zoom_center + final_size / 2).astype(int)

    tocorner = np.array([-final_size[0], final_size[1]]) / 2
    endpoints[1] = np.round(zoom_center - tocorner).astype(int)
    tocorner = np.array([final_size[0], -final_size[1]]) / 2
    endpoints[2] = np.round(zoom_center - tocorner).astype(int)

    steps += 1
    cornerpoints = np.zeros([steps, 4, 2], dtype=int)
    pixratios = np.zeros(steps)
    for i in range(4):
        for j in range(2):
            cornerpoints[:, i, j] = np.round(
                np.linspace(startpoints[i, j], endpoints[i, j], steps)
            ).astype(int)

    final_resolution = np.round(final_size * gif_resolution_to_final).astype(int)
    images = np.zeros([steps, final_resolution[0], final_resolution[1]])
    for i in range(steps):
        pixratios[i] = (
            cornerpoints[i, 1, 0] - cornerpoints[i, 0, 0]
        ) / final_resolution[0]

        roi_img = img[
            cornerpoints[i, 0, 0] : cornerpoints[i, 1, 0],
            cornerpoints[i, 0, 1] : cornerpoints[i, 2, 1],
        ]

        ratio = roi_img.shape[0] / final_resolution[0]  # size
        sigma = ratio / 4

        ksize = np.round(5 * sigma).astype(int)
        if ksize % 2 == 0:
            ksize += 1
        roi_img = cv2.GaussianBlur(roi_img, [ksize, ksize], sigma)
        images[i] = cv2.resize(roi_img, final_resolution[::-1], cv2.INTER_AREA)

    return images, pixratios

#%%  plot_sortout
def vis_plot_line_ids(image, sortout, legend=True, alpha=0.5, markersize=0.5):
    px = 1/plt.rcParams['figure.dpi']  
    plt.figure(figsize=(1200*px, 1000*px))
    plt.imshow(image, cmap="gray")
    colors = ["b", "r", "g", "c", "m", "y"]
    for j in range(len(sortout)):
        count = 0
        for i in sortout[j]:
            if count == 0:
                plt.scatter(
                    i[:, 1],
                    i[:, 0],
                    c=colors[j],
                    alpha=alpha,
                    label=str(j),
                    s=markersize,
                    edgecolors='none'
                )
            else:
                plt.scatter(
                    i[:, 1],
                    i[:, 0],
                    c=colors[j],
                    alpha=alpha,
                    s=markersize,
                    edgecolors='none'
                )
            count += 1
    if legend == True:
        plt.legend()

  
#%% interactive plotting

class line_object:
    __slots__="x","y","length","changed"
    def __init__(self, x, y,image_counter):
        self.x = [x]
        self.y = [y]
        self.length=0
        self.changed=[image_counter]


def _progress_to_next_image(next_image_counter,line_objs):
    for i in line_objs[next_image_counter-1]:
        if i in line_objs[next_image_counter]:
            change_index0=line_objs[next_image_counter-1][i].changed[-1]
            change_index1=line_objs[next_image_counter][i].changed[-1]
            
            if change_index0 > change_index1:
                line_objs[next_image_counter][i]=copy.deepcopy(line_objs[next_image_counter-1][i])
                if len(line_objs[next_image_counter][i].x)==1:
                    #print('changed is -1')
                    line_objs[next_image_counter][i].changed[-1]=-1
        else:
            line_objs[next_image_counter][i]=copy.deepcopy(line_objs[next_image_counter-1][i])
            if len(line_objs[next_image_counter][i].x)==1:
                #print('changed is -1')
                line_objs[next_image_counter][i].changed[-1]=-1


#%% image plotting
class image_plotting:
    def __init__(self,images,image_counter=0):
        
        self.images=assure_multiple(images)
        self.image_counter=image_counter
        self.line_overlay=False
        self._main_args=[]
        self._main_funcs=[]

        plt.ioff()
        self.fig,self.ax  = plt.subplots()
        self.ax.cla()

    def show(self):
        self.img_plot=self.ax.imshow(self.images[self.image_counter],cmap='gray')
        if hasattr(self,"times"):
            timestamp=" at time "+str(np.round(self.times[self.image_counter],1))+" s"
        else:                
            timestamp=""
            
        self.ax.set_title("image "+str(self.image_counter)+timestamp)

            
        warnings.simplefilter("ignore", UserWarning)
        self.fig.tight_layout()
        plt.ion()
        for i in range(len(self._main_funcs)):
            self._main_funcs[i](*self._main_args[i])
        plt.show()


    def add_keyboard(self):
        self._main_funcs.append(self.fig.canvas.mpl_connect)
        self._main_args.append(['key_press_event',self._keyboard_input])
        self.keyboard_funcs={}
        

    def _keyboard_input(self,event):
        if event.key in self.keyboard_funcs:
            self.keyboard_funcs[event.key]()
            
            if self.line_overlay:
                self._plot_overlay()
    
            plt.gcf().canvas.draw() 
        
           
    #%%% image series navigation b/n
    def addfunc_image_series(self,times=None):
        """
        navigate multiple images with 'b' and 'n'
        press 'b': go to image before  ;  'n' go to next image
        """
        if times is not None:
            self.times=times
            
        if not hasattr(self,"keyboard_funcs"):
            self.add_keyboard()
        
        self.keyboard_funcs["n"]=self._next_image
        self.keyboard_funcs["b"]=self._before_image

    def _next_image(self):
        if self.image_counter==len(self.images)-1:
            print('end of image stack')
        else:
            self.image_counter +=1    
            self.img_plot.set_data(self.images[self.image_counter])
            
            if hasattr(self,"times"):
                timestamp=" at time "+str(np.round(self.times[self.image_counter],1))+" s"
            else:                
                timestamp=""
                
            self.ax.set_title("image "+str(self.image_counter)+timestamp)
            
            
            if hasattr(self, "line_objs"):
                _progress_to_next_image(self.image_counter, self.line_objs) 

    def _before_image(self):
        if self.image_counter==0:
            print('no previous image')
        else:
            self.image_counter -=1
            self.img_plot.set_data(self.images[self.image_counter])
            
            if hasattr(self,"times"):
                timestamp=" at time "+str(np.round(self.times[self.image_counter],1))+" s"
            else:                
                timestamp=""

            self.ax.set_title("image "+str(self.image_counter)+timestamp)

    #%%% shifts
    def addfunc_shifts(self,shifts=None):
        """
        move overlays with the arrow keys
        after activating this function with 'm'
        deactivating with 'm' saves the shift
        """
        if "right" in plt.rcParams['keymap.forward']:
            plt.rcParams['keymap.forward'].remove('right')
            
        if "left" in plt.rcParams['keymap.back']:
            plt.rcParams['keymap.back'].remove('left')
        
        
        if not hasattr(self,"keyboard_funcs"):
            self.add_keyboard()
            
        if shifts is None:
            self.shifts={}
            self.shifts[0]=[0,0]
        else:
            self.shifts=copy.deepcopy(shifts)

        self.shift_active=False

        self.keyboard_funcs["m"]=self._manual_shift
        self.keyboard_funcs["up"]=self._move_up
        self.keyboard_funcs["down"]=self._move_down
        self.keyboard_funcs["left"]=self._move_left
        self.keyboard_funcs["right"]=self._move_right
            
    def _manual_shift(self):        
        shift=self.get_shift(self.image_counter, self.shifts)

        if not self.shift_active:
            print("shift activated")
            self.shift_active=True
            self.shift_activated_at=self.image_counter
            print("shift is x="+str(shift[0])+" , y="+str(shift[1]))
            if self.image_counter not in self.shifts:
                self.shifts[self.image_counter]=copy.deepcopy(shift)
            
        else:
            if self.shift_activated_at == self.image_counter:
                self.shift_active=False
                print("shift deactivated resulting with:")
                print("x="+str(shift[0])+" , y="+str(shift[1]))
    
                if self.image_counter>0:
                    oldshift=self.get_shift(self.image_counter-1, self.shifts)
                    if oldshift[0]==shift[0] and oldshift[1]==shift[1]:
                        print("no change happened")
                        del self.shifts[self.image_counter]    
            else:
                print("return to frame, where shift was activated:" +str(self.shift_activated_at))
                
                
    def _move_up(self):
        if self.shift_active:
            self.shifts[self.image_counter][1] +=1
                 
    def _move_down(self):
        if self.shift_active:
            self.shifts[self.image_counter][1] -=1
               
    def _move_left(self):
        if self.shift_active:
            self.shifts[self.image_counter][0] +=1
                
    def _move_right(self):
        if self.shift_active:
            self.shifts[self.image_counter][0] -=1
                
    @staticmethod
    def get_shift(image_counter,shifts):
        keylist=np.sort(list(shifts.keys()))[::-1]
        for i in range(len(keylist)):
            if keylist[i] <= image_counter:
                return shifts[keylist[i]]


    #%%% image overlays
    def addfunc_img_overlays(self,orig_points,overlay_imgs,overlay_points):
        """
        overlay the image with other images
        corresponding points in all images are needed
        cycle through data with 'c'
        """
        if "c" in plt.rcParams['keymap.back']:
            plt.rcParams['keymap.back'].remove('c')
        
        if not hasattr(self,"keyboard_funcs"):
            self.add_keyboard()
            
        if not hasattr(self,"shifts"):
            self.shifts={}
            self.shifts[0]=[0,0]
            
        self.img_overlay=0
        self.img_max=len(overlay_imgs)
        self.orig_points=orig_points
        self.overlay_imgs=overlay_imgs
        self.overlay_points=overlay_points
        
        self.keyboard_funcs["c"]=self._image_overlay


    def _image_overlay(self):           
        if self.img_overlay<self.img_max:
            shift=self.get_shift(self.image_counter,self.shifts)
            dim=self.images[self.image_counter].shape
            p2=copy.deepcopy(self.orig_points)
            for i in range(len(p2)):
                for j in range(2):
                    p2[i,j]-=shift[j]#[::-1]
            
            im1s,im2, matrices, reswidth, resheight, width_shift, height_shift=align_images(
                self.overlay_imgs, self.images[self.image_counter], self.overlay_points, p2,verbose=True)
            
            newim=im1s[self.img_overlay][height_shift:height_shift+dim[0],width_shift:width_shift+dim[1]]
            
            self.img_plot.set_data(newim)
            self.ax.set_title("overlay")
            self.img_overlay+=1

        else:
            self.img_overlay=0
            self.img_plot.set_data(self.images[self.image_counter])
            
            if hasattr(self,"times"):
                timestamp=" at time "+str(np.round(self.times[self.image_counter],1))+" s"
            else:                
                timestamp=""
         
            self.ax.set_title("image "+str(self.image_counter)+timestamp)

                

    #%%% line features
    def addfunc_line_features(self,line_objs=None,line_set=None):
        """
        create lines by right clicking
        pick lines by left clicking
        to unpick a line press 'i'
        to delete a line, pick it and press 'd'
        to undo the last change to a line, pick it and press 'u'
        to either show or hide the line overlay press 'l'
        """
        
        if "l" in plt.rcParams['keymap.yscale']:
            plt.rcParams['keymap.yscale'].remove('l')
            plt.rcParams['keymap.yscale'].append('y')
            print("matplotlib default keymap changed:")
            print("'keymap.yscale': ['l'] -> ['y']")
        
        if not hasattr(self,"keyboard_funcs"):
            self.add_keyboard()

        if not hasattr(self,"shifts"):
            self.shifts={}
            self.shifts[0]=[0,0]
        
        if line_objs is None:
            self.line_objs=[{} for i in range(len(self.images))]
            if line_set is None:
                self.line_set=set()
            else:
                self.line_set=line_set
                
            self.line_index=0
        else:
            self.line_objs=line_objs
            if line_set is None:
                self.line_set=set()
                for i in self.line_objs:
                    for j in i:
                        self.line_set.add(j)
            else:
                self.line_set=line_set
            self.line_index=0
            
        self.artists={}
        self.line_active=False
        self.line_activated_at=0
        self.line_delete=False
        self.line_undo=False

        self.keyboard_funcs["l"]=self._line_overlay        
        self.keyboard_funcs["i"]=self._inactivate_lines
        self.keyboard_funcs["u"]=self._undo_last_line_change
        self.keyboard_funcs["d"]=self._delete_lines
        
        self._main_funcs.append(self.fig.canvas.callbacks.connect)
        self._main_args.append(['pick_event',self._pick_lines])

        self._main_funcs.append(self.fig.canvas.mpl_connect)
        self._main_args.append(['button_press_event',self._generate_lines])  
        
        #self.addfunc_border_snapping()
        #self.addfunc_snap_to_angle()


    #%%%% line overlay
    def _line_overlay(self):
        if not self.line_overlay:
            self.line_overlay=True                
        else:
            for i in list(self.artists.keys()):
                self.artists[i].remove()
                del self.artists[i]
            self.line_overlay=False

    def _plot_overlay(self):
        shift=self.get_shift(self.image_counter, self.shifts) 
                
        for i in self.artists:
            self.artists[i].remove()
        self.artists={}
        
        for key in self.line_objs[self.image_counter]:
            
            obj=self.line_objs[self.image_counter][key]
            x=[x-shift[0] for x in obj.x ]
            y=[y-shift[1] for y in obj.y ]
            if not self.line_active:
                artist = self.ax.plot(x,y, 'x-', picker=5,alpha=0.6,c='c')[0]
            else:
                if key == self.line_index:                    
                    if self.image_counter == self.line_activated_at:
                        artist = self.ax.plot(x,y, 'x-', picker=5,alpha=0.6,c='r')[0]
                    else:
                        artist = self.ax.plot(x,y, 'x-', picker=5,alpha=0.6,c='y')[0]
                else:
                    artist = self.ax.plot(x,y, 'x-', picker=5,alpha=0.6,c='c')[0]


            artist.index = key  
            self.artists[key]=artist
            
        self.ax.set_xlim(self.ax.get_xlim())
        self.ax.set_ylim(self.ax.get_ylim())
   
    #%%%% line picking
    def _pick_lines(self,event):
        #leftclick_id=1
        if event.mouseevent.button == 1:
            self.line_index=event.artist.index
            self.line_active=True
            self.line_activated_at=self.image_counter
            
            print("line "+str(event.artist.index)+" activated")
            
            if self.line_overlay:
                self._plot_overlay()
            plt.gcf().canvas.draw()
    
    
    #%%%% line inactivating
    def _inactivate_lines(self):
        if not self.line_active:
            print("no line selected")      
        else:                
            self.line_active=False
            self.line_delete=False
            self.line_undo=False

            obj=self.line_objs[self.image_counter][self.line_index]

            if len(obj.x)==1:
                self.line_set.remove(self.line_index)
                for i in range(len(self.images)):
                    if self.line_index in self.line_objs[i]: 
                        del self.line_objs[i][self.line_index]
                        
                self.artists[self.line_index].remove()
                del self.artists[self.line_index]
                
                print("line "+str(self.line_index)+" deleted")

            else:
                print("line "+str(self.line_index)+" inactivated")
                    
        
    
    #%%%% line generating
    def _generate_lines(self,event):
        #rightclick_id=3
        if event.button == 3:
            shift=self.get_shift(self.image_counter, self.shifts)
            if not self.line_active:    
                self.line_active=True
                self.line_activated_at=self.image_counter
                self._first_point_of_line(event,shift)
                
            else:
                
                obj=self.line_objs[self.image_counter][self.line_index]
    
                if len(obj.x)==1:
                    if self.image_counter==self.line_activated_at:
                        obj=self._add_second_point_of_line(event,obj,shift)
                    else:
                        print("line must be completed in image "+str(self.line_activated_at))
                        print("otherwise delete first point of line with 'i'")
                        return
    
                else:
                    self.backup=copy.deepcopy(obj)
                    self.backup_index=self.line_index
                    obj=self._change_second_point_of_line(event,obj,shift)
                    if obj is None:
                        return
                
                    obj.changed.append(self.image_counter)
    
                
                self.line_overlay=True
                print("line "+str(self.line_index)+ " written")
                      
                self.line_active=False
                
            if self.line_overlay:
                self._plot_overlay()
                plt.gcf().canvas.draw()

    @staticmethod
    def get_next_line_index(line_set):
        if len(line_set)==0:
               max_index=-1
        else:
            max_index=max(line_set)

        if max_index >len(line_set)-1:
            for i in range(max_index):
                if i not in line_set:
                    return i
        else:
            return len(line_set)                
        
    def _first_point_of_line(self,event,shift):
        self.line_index=self.get_next_line_index(self.line_set)    
        print("add line "+str(self.line_index))
        obj=line_object(event.xdata+shift[0],event.ydata+shift[1],self.image_counter) 

        self.line_objs[self.image_counter][self.line_index]=obj

        self.line_overlay=True
        self.line_set.add(self.line_index)
        print(str(event.xdata)+" , "+str(event.ydata))    

    @staticmethod
    def _add_second_point_of_line(event,obj,shift):
        obj.x.append(event.xdata+shift[0])
        obj.y.append(event.ydata+shift[1])
        dx=obj.x[1]-obj.x[0]
        dy=obj.y[1]-obj.y[0]
        obj.length=math.sqrt(dx*dx+dy*dy)
        return obj
    
    @staticmethod
    def _change_second_point_of_line(event,obj,shift): 
        old_x=copy.deepcopy(obj.x)
        old_y=copy.deepcopy(obj.y)
        
        dist0=(event.xdata+shift[0]-obj.x[0])**2+(event.ydata+shift[1]-obj.y[0])**2
        dist1=(event.xdata+shift[0]-obj.x[1])**2+(event.ydata+shift[1]-obj.y[1])**2
        if dist0 > dist1:                   
            obj.x[1]=event.xdata+shift[0]
            obj.y[1]=event.ydata+shift[1]
        else:
            obj.x[0]=event.xdata+shift[0]
            obj.y[0]=event.ydata+shift[1]
            
        dx=obj.x[1]-obj.x[0]
        dy=obj.y[1]-obj.y[0]
        dl=math.sqrt(dx*dx+dy*dy)
        if dl < obj.length:
            print("Change not accepted, length must increase")
            obj.x=old_x 
            obj.y=old_y 
            return None
        else:
            obj.length=dl
            return obj
        

    #%%%% line undo last change  
    def _undo_last_line_change(self):
            
        if not self.line_active:
            print("no line selected")
        else:
            if not self.line_undo:
                print("change to line "+str(self.line_index)+" will be undone?")
                print("Confirm with 'u', cancel with 'i'")
                self.line_undo=True
            else:
                self.line_undo=False                       
                self.line_active=False

                obj=self.line_objs[self.image_counter][self.line_index]
                
                if len(obj.changed)<2:
                    print("to delete press 'd'")
                    
                else:
                    if not self.line_index ==self.backup_index:
                        print('backup is not aligned with active line')
                        print('backup referes to line '+str(self.backup_index))
                        print('active line refers to line '+str(self.line_index))
                    else:
                        print('change undone in images:')
                        for i in range(obj.changed[2],len(self.images)):
                            if self.backup_index in self.line_objs[i]:
                                second_last_changed=self.line_objs[self.image_counter][self.line_index].changed[-2]
                                if second_last_changed == self.backup.changed[-1]:
                                    self.line_objs[self.image_counter][self.line_index]=copy.deepcopy(self.backup)
                                    print(i)

                            

    #%%%% line deleting
    def _delete_lines(self):
        if self.line_active:
            if not self.line_delete:
                print("line "+str(self.line_index)+" will be deleted?")
                print("Confirm with 'd', cancel with 'i'")
                self.line_delete=True
            else:
                self.line_set.remove(self.line_index)
                for i in range(len(self.images)):
                    if self.line_index in self.line_objs[i]: 
                        del self.line_objs[i][self.line_index]
                        
                
                print("line "+str(self.line_index)+" deleted")
                self.line_delete=False
                self.line_active=False                    
        else:
            print("no line selected to delete")

    #%%%
    def _pick_lines_specialised(self,event):
        shift=self.get_shift(self.image_counter, self.shifts)
        #leftclick_id=1
        if event.mouseevent.button == 1:
            old_line_index=self.line_index
            old_state= self.line_active
            self.line_index=event.artist.index
            self.line_active=True
            self.line_activated_at=self.image_counter
            
            obj=self.line_objs[self.image_counter][self.line_index]
                
            if old_line_index == self.line_index and old_state:
                
                if not hasattr(self, 'end_artist_index'):
                    self.end_artist_index=0      
                    self.end_artist=self.ax.plot(obj.x[0],obj.y[0],'o',c='r',markersize=6)[0]
                elif self.end_artist_index == 0:
                    self.end_artist.remove()
                    self.end_artist_index +=1
                    self.end_artist=self.ax.plot(obj.x[1],obj.y[1],'o',c='r',markersize=6)[0]
                    
                else:
                    self.end_artist.remove()
                    del self.end_artist
                    del self.end_artist_index
                       
            elif self.redirect_connect:
                self.ending_states[old_line_index][self.end_artist_index].append(self.line_index)
                self.redirect_connect=False
                print(str(old_line_index)+ " connected with "+str(self.line_index))
                
                old_obj=self.line_objs[self.image_counter][old_line_index]
                
                dist0=(obj.x[0]-old_obj.x[self.end_artist_index])**2 + (obj.y[0]-old_obj.y[self.end_artist_index])**2
                dist1=(obj.x[1]-old_obj.x[self.end_artist_index])**2 + (obj.y[1]-old_obj.y[self.end_artist_index])**2

                if dist1 > dist0:
                    new_index=0
                else:
                    new_index=1
                
                if self.line_index in self.ending_states:
                    if len(self.ending_states[self.line_index][new_index])==0:
                        self.ending_states[self.line_index][new_index]+=[self.image_counter,old_line_index]
                        print(str(self.line_index)+ " connected with "+str(old_line_index))
                    else:
                        print("line " +str(self.line_index)+' ending '+str(new_index)
                              +' state already determined')
                else:
                    self.ending_states[self.line_index]=[[],[]]
                    self.ending_states[self.line_index][new_index]+=[self.image_counter,old_line_index]
                    print(str(self.line_index)+ " connected with "+str(old_line_index))

                
                
                
            else:
                print("line "+str(event.artist.index)+" activated")
                if hasattr(self, 'end_artist_index'):
                    self.end_artist.remove()
                    del self.end_artist
                    del self.end_artist_index      
                
            if self.line_overlay:
                self._plot_overlay()
            plt.gcf().canvas.draw()


    #%%%
    def _mark_exit(self):
        if self.line_active==False:
            if hasattr(self, 'show_endings'):
                for i in self.show_endings:
                    i.remove()
                del self.show_endings
            else:
                self.show_endings=[]
                for i in self.ending_states:
                    for j in range(2):
                        if len(self.ending_states[i][j])>0:
                            obj=self.line_objs[self.image_counter][i]
                            xc=obj.x[j]
                            yc=obj.y[j]    
                            self.show_endings.append(self.ax.plot(xc,yc,'o',c='c',markersize=6)[0])

            if self.line_overlay:
                self._plot_overlay()
            plt.gcf().canvas.draw()
                    
            
        else:
            if hasattr(self, 'end_artist_index'):
                if self.line_index in self.ending_states:
                    if len(self.ending_states[self.line_index][self.end_artist_index])==0:
                        self.ending_states[self.line_index][self.end_artist_index]+=[self.image_counter,-1]
                        print("line " +str(self.line_index)+' ending '+str(self.end_artist_index)
                              +str(" marked as 'exited region of interest'"))
                    else:
                        print('ending state already determined')
                else:
                    self.ending_states[self.line_index]=[[],[]]
                    self.ending_states[self.line_index][self.end_artist_index]+=[self.image_counter,-1]
                    print("line " +str(self.line_index)+' ending '+str(self.end_artist_index)
                          +str(" marked as 'exited region of interest'"))
            else:
                print("no endpoint active to mark")

    def _mark_redirection(self):
        if hasattr(self, 'end_artist_index'):
            
            
            self.redirect_connect=True

            if self.line_index in self.ending_states:
                if len(self.ending_states[self.line_index][self.end_artist_index])==0:
                    self.ending_states[self.line_index][self.end_artist_index]+=[self.image_counter]
                    print("line " +str(self.line_index)+' ending '+str(self.end_artist_index)
                        +" marked for connection")
                else:
                    print('ending state already determined')
            else:
                self.ending_states[self.line_index]=[[],[]]
                self.ending_states[self.line_index][self.end_artist_index]+=[self.image_counter]
                print("line " +str(self.line_index)+' ending '+str(self.end_artist_index)
                    +" marked for connection")

        else:
            print("no endpoint active to mark")


    def _mark_double(self):
        if hasattr(self, 'end_artist_index'):
            if self.line_index in self.ending_states:
                if len(self.ending_states[self.line_index][self.end_artist_index])>-1:
                    if self.line_index in self.doubles:
                        self.doubles[self.line_index][self.end_artist_index]=True
                    else:
                        self.doubles[self.line_index]=np.zeros(2,dtype=bool)
                        self.doubles[self.line_index][self.end_artist_index]=True
                    print("line " +str(self.line_index)+' ending '+str(self.end_artist_index)
                        +" marked as double line")
            else:
                print("redirect connect must be applied before")
        else:
            print("no endpoint active to mark")

    #%% Filter for details
    def addfunc_endpoint_details(self):
        """
        pick lines by left clicking
        to unpick a line press 'i'
        to delete a line, pick it and press 'd'
        to undo the last change to a line, pick it and press 'u'
        to either show or hide the line overlay press 'l'
        """
        
        if not ['pick_event',self._pick_lines] in self._main_args:
            print("line_features necessary")
        
        if not hasattr(self,"keyboard_funcs"):
            self.add_keyboard()
            
            
        self.keyboard_funcs["w"]=self._mark_double            
        self.keyboard_funcs["e"]=self._mark_exit
        self.keyboard_funcs["r"]=self._mark_redirection
        
        self._main_args.remove(['pick_event',self._pick_lines])
        self._main_args.append(['pick_event',self._pick_lines_specialised])
        
        self.ending_states={}
        self.doubles={}
        self.redirect_connect=False
        

    #%% Text input
    def addfunc_text_input(self):
        self.axbox = self.fig.add_axes([0.05, 0.05, 0.05, 0.075])
        self.text_box = TextBox(self.axbox, "Goto", textalignment="center")
        self.text_box.set_val("0")
        self._main_funcs.append(self.text_box.on_submit)
        self._main_args.append([self._text_input])
    
    def _text_input(self,expression):
        new_image_counter=int(expression)
        if new_image_counter < self.image_counter:
            pass
        else:
            for i in range(self.image_counter+1,new_image_counter+1):
                _progress_to_next_image(i,self.line_objs)
                
        self.image_counter=new_image_counter
        self.img_plot.set_data(self.images[self.image_counter])
        
        if hasattr(self,"times"):
            timestamp=" at time "+str(np.round(self.times[self.image_counter],1))+" s"
        else:                
            timestamp=""
            
        self.ax.set_title("image "+str(self.image_counter)+timestamp)
        
        if self.line_overlay:
            self._plot_overlay()
            plt.gcf().canvas.draw()
        
        


    #%% save as json        
    def addfunc_save_as_json(self,filepath):
        """
        save lines and shifts as .json with 's'
        filepath needed
        """
        self.filepath=filepath
        if "s" in plt.rcParams['keymap.save']:
            plt.rcParams['keymap.save'].remove('s')

        self.keyboard_funcs["s"]=self._save_lines_and_shifts     


    def _save_lines_and_shifts(self):
        print('start saving')
        save_line_objs=[{} for i in range(len(self.images))]
        for i in range(len(self.images)):
            for j in self.line_objs[i]:
                save_line_objs[i][j]={}
                save_line_objs[i][j]['x']=self.line_objs[i][j].x
                save_line_objs[i][j]['y']=self.line_objs[i][j].y
                save_line_objs[i][j]['length']=self.line_objs[i][j].length
                save_line_objs[i][j]['changed']=self.line_objs[i][j].changed
                
        with open(self.filepath, 'w') as fp:
            json.dump([save_line_objs,self.shifts], fp)

        str_index=self.filepath[::-1].find('.')
        fp2=self.filepath[:-str_index-1]
        fp2 += '_set.json'
        
        with open(fp2, 'w') as fp:
            json.dump(list(self.line_set), fp)
            
        print("saved to "+self.filepath)


def save_as_json(filepath,line_objs,shifts,line_set):
    print('start saving')
    save_line_objs=[{} for i in range(len(line_objs))]
    for i in range(len(line_objs)):
        for j in line_objs[i]:
            save_line_objs[i][j]={}
            save_line_objs[i][j]['x']=line_objs[i][j].x
            save_line_objs[i][j]['y']=line_objs[i][j].y
            save_line_objs[i][j]['length']=line_objs[i][j].length
            save_line_objs[i][j]['changed']=line_objs[i][j].changed
         
    with open(filepath, 'w') as fp:
        json.dump([save_line_objs,shifts], fp)
    
    str_index=filepath[::-1].find('.')
    fp2=filepath[:-str_index-1]
    fp2 += '_set.json'
    
    with open(fp2, 'w') as fp:
        json.dump(list(line_set), fp)
    
    print("saved to "+filepath)
    

def read_in_json_old(filepath):
    with open(filepath, 'r') as fp:
        save_line_objs,save_shifts = json.load(fp)
    
    shifts={}    
    for i in save_shifts:
        shifts[int(i)]=save_shifts[i]
    
    line_objs=[{} for i in range(len(save_line_objs))]
    for i in range(len(save_line_objs)):
        for j in save_line_objs[i]:
            obj=line_object(0,0,0)
            obj.x=save_line_objs[i][j]['x'] 
            obj.y=save_line_objs[i][j]['y']
            obj.length=save_line_objs[i][j]['length']
            obj.changed=save_line_objs[i][j]['changed']
            line_objs[int(i)][int(j)]=obj
        
    
    return line_objs,shifts

#%%
def read_in_json(filepath):
    with open(filepath, 'r') as fp:
        save_line_objs,save_shifts = json.load(fp)

    str_index=filepath[::-1].find('.')
    fp2=filepath[:-str_index-1]
    fp2 += '_set.json'

    with open(fp2, 'r') as fp:
        line_set = json.load(fp)
    
    line_set=set(line_set)
    
    print('test')
    
    shifts={}    
    for i in save_shifts:
        shifts[int(i)]=save_shifts[i]
    
    line_objs=[{} for i in range(len(save_line_objs))]
    for i in range(len(save_line_objs)):
        for j in save_line_objs[i]:
            obj=line_object(0,0,0)
            obj.x=save_line_objs[i][j]['x'] 
            obj.y=save_line_objs[i][j]['y']
            obj.length=save_line_objs[i][j]['length']
            obj.changed=save_line_objs[i][j]['changed']
            line_objs[int(i)][int(j)]=obj
        
    
    return line_objs,shifts,line_set        
        
        

