# -*- coding: utf-8 -*-
"""
@author: kernke
"""
import numpy as np
from .image_processing import img_rotate_bound
from .general_util import make_mask
import matplotlib.pyplot as plt
import cv2
from scipy import ndimage
from scipy.spatial.distance import cdist


#%% optimal rotation /deprecated
# deprecated
def optimal_rotation(image_roi, angle, thresh=5, minlength=50, line="dark", show=False):
    # image_roi should contain lines with the respective angle, optimally not ending inside the ROI
    # angle in degree

    # optimal angle is determined by the two characteristics of a misfit line:
    # lower brightness
    # lower brightness variance

    pmangle = np.arange(-3, 4)

    dummy = np.ones(np.shape(image_roi))

    for k in range(5):
        snr = np.zeros(7)
        for i in range(7):
            rot, log = img_rotate_bound(image_roi, angle + pmangle[i])
            drot, log = img_rotate_bound(dummy, angle + pmangle[i], bm=0)
            mask = drot > 0.1
            # rot -= pr/5

            snr[i] = obtain_snr(rot, mask, line, False, minlength)

        # plt.plot(snr)
        # plt.show()

        if np.max(snr) < thresh:
            print(np.max(snr))
            print("signal to noise ratio below threshold")
            return False

        angle += pmangle[np.argmax(snr)]
        pmangle = pmangle / 3

    res = np.round(angle, 2)

    if show:
        rot, log = img_rotate_bound(image_roi, res)
        drot, log = img_rotate_bound(dummy, res, bm=0)
        mask = drot > 0.1
        # obtain_snr(rot, mask, line,True,minlength)
        plt.imshow(rot * mask)
        plt.show()

    return res


#%% obtain snr  for optimal rotation / deprecated
# deprecated
def obtain_snr(image, mask, line, show, minlength):

    rmeans = []
    rstds = []

    for j in range(image.shape[0]):
        roi = image[j][mask[j]]

        if len(roi) < minlength:
            pass
        else:
            rmeans.append(np.mean(roi))
            rstds.append(np.mean(np.sqrt((roi - rmeans[-1]) ** 2)) / np.sqrt(len(roi)))

    rmeans = np.array(rmeans)
    x = np.arange(len(rmeans))
    p = np.polyfit(x, rmeans, 5)
    rmeans -= np.polyval(p, x)
    rstds = np.array(rstds)

    val = rmeans / rstds
    if line == "dark":
        val = np.mean(val) - val
    elif line == "bright":
        val -= np.mean(val)

    vstd = np.std(val)

    if show:
        val2 = val - np.min(val)
        plt.plot(val2 * 1 / np.max(val2), c="r")
        plt.show()

    return np.max(val) / vstd



#%% enhance_lines_prototype
def enhance_lines_prototype(
    image, angle, ksize=None, dist=1, iterations=2, line="dark"
):

    if ksize is None:
        ksize=3
    
    dummy = np.ones(image.shape)
    rot, log = img_rotate_bound(image, angle)
    drot, log = img_rotate_bound(dummy, angle, bm=0)
    newmask = make_mask(drot, 2)

    trot = np.clip(rot, np.min(image), np.max(image))
    if line == "dark":
        trot -= np.min(trot)
        trot = np.max(trot) - trot
    elif line == "bright":
        pass

    tres = trot / np.max(trot) * 255

    # res=np.copy(tres)

    for i in range(iterations):

        srot = cv2.Sobel(tres, cv2.CV_64F, 0, 1, ksize=ksize)

        msrot = np.ma.array(srot, mask=np.invert(newmask))

        middle = np.mean(msrot)

        t1 = srot > middle
        t2 = srot <= middle

        tres = np.zeros(srot.shape)
        tres[:-dist, :] -= t2[dist:, :] * (srot[dist:, :] - middle)
        tres[dist:, :] += t1[:-dist, :] * (srot[:-dist, :] - middle)
        # res *= tres

    return tres * newmask, newmask, log

#%%
def normalized_spectra(data,se_image,wavelengths,boundary_offset=0,minimum_pix=25,
                       ksize1=20,ksize2=40,ksize3=10,upper_threshold=1.1,lower_threshold=0.95):
    """
    ksize1:proportional to the boundary between island and ring
    ksize2:proportional to the width of the ring
    ksize3:closing gaps in the mask to obtain the spectrum of SiO
    """
    # obtain binary image with areas holding the value 1 represent the crystal islands
    # and the area with value 0 is the SiO-matrix
    binary_image=se_image>np.mean(se_image)*upper_threshold
    binary_image=binary_image*1
    if boundary_offset>0:
        mask=np.zeros(binary_image.shape)
        mask[boundary_offset:-boundary_offset,boundary_offset:-boundary_offset]=1
        binary_image=(binary_image*mask).astype(np.uint8)

    # label all the islands, that contain atleast the minimum amount of pixels
    # also get a center-position of island by a mean of all pixel-positions of that island
    separated_image,number_of_islands=ndimage.label(binary_image)
    spots=[]
    centers=[]
    for i in range(number_of_islands):
        index1,index2=np.where(separated_image==i)
        if len(index1)<minimum_pix:
            pass
        else:
            if i ==0:
                #pass
                si_matrix=(index1,index2)
            else:
                x=np.mean(index1)
                y=np.mean(index2)
                centers.append((x,y))
                spots.append((index1,index2))

    # get the actual CL-spectrum of each island, 
    # by taking the mean over the pixels of each island at the respective wavelength   
    spectra=np.zeros([len(spots),len(wavelengths)])
    for k in range(len(wavelengths)):
        for i in range(len(spots)):
            index1,index2=spots[i]
            spot_pixels=np.zeros(len(index1))
            for j in range(len(index1)):
                spot_pixels[j]=data[k,index1[j],index2[j]]
            
            spectra[i,k]=np.mean(spot_pixels)


    
    # To obtain a spectrum of the SiO-matrix, we want to make sure to not get any effect from the nano-islands
    # or the spots, where the SiO-matrix is interrupted with no island
    # so now we create a mask not only using a threshold for the bright islands (upper_threshold)
    # but also a threshold for the dark spots, where no islands sit anymore (lower_threshold)
    center=(ksize3-1)//2
    kernel=cv2.circle(np.zeros([ksize3,ksize3],dtype=np.uint8),(center,center),center,1,-1)
    SiO_image=(se_image<np.mean(se_image)*upper_threshold) * (se_image>np.median(se_image)*lower_threshold )*1.
    if boundary_offset>0:
        SiO_image=SiO_image*mask
    SiO_image=cv2.erode(SiO_image,kernel)

    # Show the result next to the original SEM-image
    fig,ax=plt.subplots(1,3)
    fig.set_figwidth(12)
    ax[1].imshow(se_image,cmap="gray")
    ax[1].set_title("original SEM-image")
    ax[0].imshow(binary_image)
    ax[0].set_title("obtained mask/binary image")
    ax[2].imshow(SiO_image)
    ax[2].set_title("yellow area for SiO-spectrum")
    plt.show()
    
    # get the mean background
    mean_background=np.zeros(len(wavelengths))
    for k in range(len(wavelengths)):
        mean_background[k]=np.mean(data[k][SiO_image==1])

    # For that reason we increase the masked area of the island 
    center=(ksize1-1)//2
    kernel=cv2.circle(np.zeros([ksize1,ksize1],dtype=np.uint8),(center,center),center,1,-1)
    si_matrix_mask=np.zeros(binary_image.shape,dtype=np.uint8)
    index1,index2=si_matrix
    si_matrix_mask[index1,index2]=1
    si_matrix_mask2=cv2.erode(si_matrix_mask,kernel)



    # by increasing the masked area further and subtracting the original mask,
    # we obtain rings surrounding each spot, 
    # which we can use to subtract the local background at each spot.
    center=(ksize2-1)//2
    kernel=cv2.circle(np.zeros([ksize2,ksize2],dtype=np.uint8),(center,center),center,1,-1)
    si_matrix_mask3=cv2.erode(si_matrix_mask2,kernel)
    ring_image=si_matrix_mask3-si_matrix_mask2

    separated_image,number_of_islands=ndimage.label(ring_image)
    rings=[]
    rcenters=[]
    for i in range(number_of_islands):
        index1,index2=np.where(separated_image==i)
        if len(index1)<minimum_pix:
            pass
        else:
            if i ==0:
                pass
            else:
                x=np.mean(index1)
                y=np.mean(index2)
                rcenters.append((x,y))
                rings.append((index1,index2))

    fig,ax=plt.subplots(1,3)
    fig.set_figwidth(12)
    ax[0].imshow(binary_image)
    ax[0].set_title("labeled islands")
    counter=0
    for i in centers:
        ax[0].text(i[1],i[0],str(counter),c="r")
        counter+=1
    ax[1].imshow(si_matrix_mask2)
    ax[1].set_title("increased island areas (inside of rings)")
    ax[2].imshow(ring_image)
    ax[2].set_title("rings for local background-subtraction")
    plt.show()

    # Because some islands are very close to each other,
    # they are surrounded by a single ring.
    # Thus the number of islands is not the same as the number of rings.
    # So we calculate the distance of the center of each island to the center of each ring,
    # the the island and the ring with minimal distance are paired 
    distance_matrix=cdist(centers,rcenters)
    spot_ring_relation=np.argmin(distance_matrix,axis=1)

    # obtain the spectra of the all the rings    
    rspectra=np.zeros([len(rings),len(wavelengths)])
    for k in range(len(wavelengths)):
        for i in range(len(rings)):
            index1,index2=rings[i]
            ring_pixels=np.zeros(len(index1))
            for j in range(len(index1)):
                ring_pixels[j]=data[k,index1[j],index2[j]]
            
            rspectra[i,k]=np.mean(ring_pixels)

    # subtract the local background by the corresponding ring from each island
    # also correct brightness variations in the image, due to the mirror-geometry
    # by normalizing the local SiO(ring)-spectra by the mean-SiO-spectrum
    nspectra=np.zeros(spectra.shape)
    for k in range(len(wavelengths)):
        for i in range(len(spots)):
            nspectra[i,k]=spectra[i,k]-rspectra[spot_ring_relation[i],k]
            #fac=mean_background[k]/rspectra[i,k]
            nspectra[i,k] *= mean_background[k]/rspectra[spot_ring_relation[i],k]
            
    return nspectra,mean_background,centers

#%% eliminate_side_maxima_image
"""
    def eliminate_side_maxima_image(
        self, image, shiftrange=2, tol=1, valfactor=2.5, line="dark", test=False
    ):
        tms = self.slope_groups
        conpois = self.conpois
        # image=self.image
            #imcheck= _check_image(conpois[i], conlens[i], checkmaps[i])
            #if line == 'dark':
            #    cond=imcheck>medbrightness*med_ratio_threshold
            #else:
            #    cond=imcheck*med_ratio_threshold<medbrightness


        sortoutids = []
        sortout = []

        if line == "bright":

            for i in range(len(conpois)):
                sortout.append([])
                sortoutids.append([])

                if tms[i] > 1:
                    for j in range(len(conpois[i])):
                        check = _getcheck1(shiftrange, conpois[i][j], image)

                        vcheck = np.max(check[shiftrange - tol : shiftrange + tol])
                        check = check[check.astype(bool)]
                        checkmed = np.median(check)

                        if vcheck < valfactor * checkmed:

                            sortout[-1].append(conpois[i][j])
                            sortoutids[-1].append(j)

                else:
                    for j in range(len(conpois[i])):
                        check = _getcheck0(shiftrange, conpois[i][j], image)

                        vcheck = np.max(check[shiftrange - tol : shiftrange + tol])
                        check = check[check.astype(bool)]
                        checkmed = np.median(check)
                        if vcheck < valfactor * checkmed:
                            sortout[-1].append(conpois[i][j])
                            sortoutids[-1].append(j)

                print(len(sortout[-1]))

        else:
            for i in range(len(conpois)):
                sortout.append([])
                sortoutids.append([])

                if tms[i] > 1:
                    for j in range(len(conpois[i])):
                        check = _getcheck1(shiftrange, conpois[i][j], image)

                        vcheck = np.max(check[shiftrange - tol : shiftrange + tol])
                        check = check[check.astype(bool)]
                        checkmed = np.median(check)

                        if vcheck > valfactor * checkmed:

                            sortout[-1].append(conpois[i][j])
                            sortoutids[-1].append(j)

                else:
                    for j in range(len(conpois[i])):
                        check = _getcheck0(shiftrange, conpois[i][j], image)

                        vcheck = np.max(check[shiftrange - tol : shiftrange + tol])
                        check = check[check.astype(bool)]
                        checkmed = np.median(check)
                        if vcheck > valfactor * checkmed:
                            sortout[-1].append(conpois[i][j])
                            sortoutids[-1].append(j)

                print(len(sortout[-1]))

        if not test:
            self.sort_ids_out(sortoutids)

        return sortout
"""
#%% Enhance Lines2
"""
def line_enhance2(
    image, angle, ksize=None, dist=1, iterations=2, line="dark"
):

    if len(np.shape(dist)) == 0:
        dist = [dist]

    dummy = np.ones(image.shape)
    rot, log = img_rotate_bound(image, angle)
    drot, log = img_rotate_bound(dummy, angle, bm=0)
    newmask = make_mask(drot, 2)

    trot = np.clip(rot, np.min(image), np.max(image))
    if line == "dark":
        trot -= np.min(trot)
        trot = np.max(trot) - trot
    elif line == "bright":
        pass

    tres = trot / np.max(trot) * 255

    res = np.copy(tres)

    for i in range(iterations):
        if ksize is None:
            srot = cv2.Sobel(tres, cv2.CV_64F, 0, 1)
        else:
            srot = cv2.Sobel(tres, cv2.CV_64F, 0, 1, ksize=ksize)

        msrot = np.ma.array(srot, mask=np.invert(newmask))

        middle = np.median(msrot)

        t1 = srot > middle
        t2 = srot <= middle

        tres2 = np.zeros([len(dist), srot.shape[0], srot.shape[1]])
        for j in range(len(dist)):
            tres2[j, : -dist[j], :] -= t2[dist[j] :, :] * (srot[dist[j] :, :] - middle)
            tres2[j, dist[j] :, :] += t1[: -dist[j], :] * (srot[: -dist[j], :] - middle)
        tres = np.sum(tres2, axis=0)
        res *= tres

    return (
        res ** (1 / (iterations + 1)) * newmask,
        newmask,
        log,
        trot / np.max(trot) * 255,
    )
"""
#%% Enhance Lines
"""
def line_enhance(
    image, angle, ksize=None, dist=1, iterations=2, line="dark"
):

    dummy = np.ones(image.shape)
    rot, log = img_rotate_bound(image, angle)
    drot, log = img_rotate_bound(dummy, angle, bm=0)
    newmask = make_mask(drot, 2)

    trot = np.clip(rot, np.min(image), np.max(image))
    if line == "dark":
        trot -= np.min(trot)
        trot = np.max(trot) - trot
    elif line == "bright":
        pass

    tres = trot / np.max(trot) * 255

    res = np.copy(tres)

    for i in range(iterations):
        if ksize is None:
            srot = cv2.Sobel(tres, cv2.CV_64F, 0, 1)
        else:
            srot = cv2.Sobel(tres, cv2.CV_64F, 0, 1, ksize=ksize)

        msrot = np.ma.array(srot, mask=np.invert(newmask))

        middle = np.median(msrot)

        t1 = srot > middle
        t2 = srot <= middle

        tres = np.zeros(srot.shape)

        tres[:-dist, :] -= t2[dist:, :] * (srot[dist:, :] - middle)
        tres[dist:, :] += t1[:-dist, :] * (srot[:-dist, :] - middle)

        res *= tres

    return (
        res ** (1 / (iterations + 1)) * newmask,
        newmask,
        log,
    )  

"""
#%% process2
"""
# smoothsize=35
def line_process2(
    images,
    rotangles,
    lowhigh,
    ksize_erodil=15,
    ksize_anms=15,#19
    damp=10,
    smoothsize=1,
    Hthreshold=50,
    Hminlength=5,
    Hmaxgap=50,
    line="dark",
    ksize=None,
    iterations=2,
    anms_threshold=2,
    dist=1,
    houghdist=1,
):
    qkeys = []
    qkeys = list(images.keys())

    qcheck_images = {}

    for m in range(len(qkeys)):
        line_images = []
        check_images = []
        image = images[qkeys[m]]

        print(str(m + 1) + " / " + str(len(qkeys)))
        print(qkeys[m])
        for k in range(len(rotangles)):
            tres, newmask, log, rotimg = line_enhance2(
                image,
                rotangles[k],
                iterations=iterations,
                ksize=ksize,
                line=line,
                dist=dist,
            )

            nms = img_anms(
                tres,
                newmask,
                thresh_ratio=anms_threshold,
                ksize=ksize_anms,
                damping=damp,
            )  

            clean = img_noise_line_suppression(nms, ksize_erodil)

            clean = clean / np.max(clean) * 255

            nclean = np.zeros(clean.shape, dtype=np.double)
            nclean += clean
            nclean += rotimg

            nclean = img_to_uint8(nclean)

            #new = nclean[newmask > 0]

            check_images.append(img_rotate_back(nclean, log))
            #line_images.append(np.zeros(check_images[-1].shape))

        qcheck_images[qkeys[m]] = check_images
        
        xmax = lowhigh[qkeys[-1]][0][0] + qcheck_images[qkeys[-1]][0].shape[0]
        ymax = lowhigh[qkeys[-1]][1][0] + qcheck_images[qkeys[-1]][0].shape[1]

        nangles = len(qcheck_images[qkeys[0]])

        checkmaps = np.zeros([nangles, xmax, ymax])
        
        for i in qkeys:
            xmin = lowhigh[i][0][0]
            ymin = lowhigh[i][1][0]
            ishape = qcheck_images[i][0].shape

            for j in range(nangles):
                checkmaps[
                    j, xmin : xmin + ishape[0], ymin : ymin + ishape[1]
                ] += qcheck_images[i][j]
        


    return check_images
"""

#%% eliminate_side_maxima_image
"""
    def eliminate_side_maxima_image(self,shiftrange=2,tol=1,line='dark',test=False):
        tms=self.tms
        conpois=self.conpois
        image=self.image

        sortoutids=[]
        sortout=[]

        for i in range(len(conpois)):
            sortout.append([])
            sortoutids.append([])

            #image=checkmaps[i]
            if tms[i]>1:
                for j in range(len(conpois[i])):

                    #a=np.max(conpois[i][j][:,1])
                    #b=np.min(conpois[i][j][:,1])
                    #if a+shiftrange >= image.shape[1] or b-shiftrange<0:
                    #    pass
                    #else:
                    check=getcheck1(shiftrange,conpois[i][j],image)

                    icheck=np.argmax(check)
                    checkval=np.max(check)
                    #print(icheck)
                    if icheck < shiftrange-tol or icheck > shiftrange+tol:

                        #checkmedian=np.median(check)
                        #mad=np.median(np.abs(check-checkmedian))
                        #if check[shiftrange] < checkmedian+mad_threshold*mad:
                        sortout[-1].append(conpois[i][j])
                        sortoutids[-1].append(j)

            else:
                for j in range(len(conpois[i])):

                    #a=np.max(conpois[i][j][:,0])
                    #b=np.min(conpois[i][j][:,0])
                    #if a+shiftrange >= image.shape[0] or b-shiftrange<0:
                    #    pass
                    #else:
                    check=getcheck0(shiftrange,conpois[i][j],image)
                    icheck=np.argmax(check)
                    #print(icheck)

                    if icheck < shiftrange-tol or icheck > shiftrange+tol:

                        #checkmedian=np.median(check)
                        #mad=np.median(np.abs(check-checkmedian))
                        #if check[shiftrange] < checkmedian+mad_threshold*mad:
                        sortout[-1].append(conpois[i][j])
                        sortoutids[-1].append(j)

            print(len(sortout[-1]))

        if not test:
            self.sort_ids_out(sortoutids)

        return sortout
    
"""   
    
    #%% make_interaction_dictionnary
"""
    def make_interaction_dictionnary(self):
        
        ext_slists = self.extended_slists
        shr_slists = self.shrinked_slists
        ext_elists = self.extended_elists
        shr_elists = self.shrinked_elists
        
        check_ext_shr_intersection(ext_slists,shr_slists,ext_elists,shr_elists)
        
        
        crosslines = self.crosslines
        crosslineset = set(map(tuple, crosslines))
        s1 = self.all
        s2 = self.cross_and_block
        s3 = self.crossings

        slists = self.extended_slists
        elists = self.extended_elists

        blockings = s2.difference(s3)
        corners = s1.difference(s2)
        gothroughs = s3


        corners_dic = {}
        gothroughs_dic = {}
        blockings_dic = {}

        for i in corners:
            (i1, i2), (i3, i4) = i
            a = slists[i1][i2]
            b = elists[i1][i2]
            c = slists[i3][i4]
            d = elists[i3][i4]
            corners_dic[i] = lineIntersection(a, b, c, d)

        for i in blockings:
            (i1, i2), (i3, i4) = i
            a = slists[i1][i2]
            b = elists[i1][i2]
            c = slists[i3][i4]
            d = elists[i3][i4]
            blockings_dic[i] = lineIntersection(a, b, c, d)

        for i in gothroughs:
            (i1, i2), (i3, i4) = i
            a = slists[i1][i2]
            b = elists[i1][i2]
            c = slists[i3][i4]
            d = elists[i3][i4]
            gothroughs_dic[i] = lineIntersection(a, b, c, d)

        return corners_dic, blockings_dic, gothroughs_dic
"""
    #%% get_line_lengths
"""    
    def _get_line_lengths(self):
        slists = self.slists
        elists = self.elists

        lengths = []

        for i in range(len(slists)):
            lengths.append([])
            for j in range(len(slists[i])):
                d = slists[i][j] - elists[i][j]
                lengths[-1].append(math.sqrt(np.sum(d * d)))

        self.lengths = lengths
        _add_attr("lengths", self.line_vars)

"""


    #%% eliminate_side_maxima
"""    
    def eliminate_side_maxima(self, mad_threshold=2, shiftrange=10, test=False):
        tms = self.slope_groups
        conpois = self.conpois
        checkmaps = self.checkmaps

        sortoutids = []
        sortout = []

        for i in range(len(conpois)):
            sortout.append([])
            sortoutids.append([])

            image = checkmaps[i]
            if tms[i] > 1:
                for j in range(len(conpois[i])):

                    a = np.max(conpois[i][j][:, 1])
                    b = np.min(conpois[i][j][:, 1])
                    if a + shiftrange >= image.shape[1] or b - shiftrange < 0:
                        pass
                    else:
                        check = _getcheck1(shiftrange, conpois[i][j], image)
                        if np.argmax(check) != shiftrange:

                            checkmedian = np.median(check)
                            mad = np.median(np.abs(check - checkmedian))
                            if check[shiftrange] < checkmedian + mad_threshold * mad:
                                sortout[-1].append(conpois[i][j])
                                sortoutids[-1].append(j)

            else:
                for j in range(len(conpois[i])):

                    a = np.max(conpois[i][j][:, 0])
                    b = np.min(conpois[i][j][:, 0])
                    if a + shiftrange >= image.shape[0] or b - shiftrange < 0:
                        pass
                    else:
                        check = _getcheck0(shiftrange, conpois[i][j], image)
                        if np.argmax(check) != shiftrange:

                            checkmedian = np.median(check)
                            mad = np.median(np.abs(check - checkmedian))
                            if check[shiftrange] < checkmedian + mad_threshold * mad:
                                sortout[-1].append(conpois[i][j])
                                sortoutids[-1].append(j)

            print(len(sortout[-1]))

        if not test:
            self.sort_ids_out(sortoutids)

        return sortout

"""
