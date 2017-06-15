# Copyright (C) 2014 Daniel Lee <lee.daniel.1986@gmail.com>
#
# This file is part of StereoVision.
#
# StereoVision is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# StereoVision is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with StereoVision.  If not, see <http://www.gnu.org/licenses/>.

"""
Classes for calibrating homemade stereo cameras.

Classes:

    * ``StereoCalibration`` - Calibration for stereo camera
    * ``StereoCalibrator`` - Class to calibrate stereo camera with

.. image:: classes_calibration.svg
"""

import os

import cv2

import numpy as np


class StereoCalibration(object):

    """
    A stereo camera calibration.

    The ``StereoCalibration`` stores the calibration for a stereo pair. It can
    also rectify pictures taken from its stereo pair.
    """

    def __str__(self):
        output = ""
        for key, item in self.__dict__.items():
            output += key + ":\n"
            output += str(item) + "\n"
        return output

    def _copy_calibration(self, calibration):
        """Copy another ``StereoCalibration`` object's values."""
        for key, item in calibration.__dict__.items():
            self.__dict__[key] = item

    def _interact_with_folder(self, output_folder, action):
        """
        Export/import matrices as *.npy files to/from an output folder.

        ``action`` is a string. It determines whether the method reads or writes
        to disk. It must have one of the following values: ('r', 'w').
        """
        if not action in ('r', 'w'):
            raise ValueError("action must be either 'r' or 'w'.")
        for key, item in self.__dict__.items():
            if isinstance(item, dict):
                for side in ("left", "right"):
                    filename = os.path.join(output_folder,
                                            "{}_{}.npy".format(key, side))
                    if action == 'w':
                        np.save(filename, self.__dict__[key][side])
                    else:
                        self.__dict__[key][side] = np.load(filename)
            else:
                filename = os.path.join(output_folder, "{}.npy".format(key))
                if action == 'w':
                    np.save(filename, self.__dict__[key])
                else:
                    self.__dict__[key] = np.load(filename)

    def __init__(self, calibration=None, input_folder=None):
        """
        Initialize camera calibration.

        If another calibration object is provided, copy its values. If an input
        folder is provided, load ``*.npy`` files from that folder. An input
        folder overwrites a calibration object.
        """
        #: Camera matrices (M)
        self.cam_mats = {"left": None, "right": None}
        #: Distortion coefficients (D)
        self.dist_coefs = {"left": None, "right": None}
        #: Rotation matrix (R)
        self.rot_mat = None
        #: Translation vector (T)
        self.trans_vec = None
        #: Essential matrix (E)
        self.e_mat = None
        #: Fundamental matrix (F)
        self.f_mat = None
        #: Rectification transforms (3x3 rectification matrix R1 / R2)
        self.rect_trans = {"left": None, "right": None}
        #: Projection matrices (3x4 projection matrix P1 / P2)
        self.proj_mats = {"left": None, "right": None}
        #: Disparity to depth mapping matrix (4x4 matrix, Q)
        self.disp_to_depth_mat = None
        #: Bounding boxes of valid pixels
        self.valid_boxes = {"left": None, "right": None}
        #: Undistortion maps for remapping
        self.undistortion_map = {"left": None, "right": None}
        #: Rectification maps for remapping
        self.rectification_map = {"left": None, "right": None}
        if calibration:
            self._copy_calibration(calibration)
        elif input_folder:
            self.load(input_folder)

    def load(self, input_folder):
        """Load values from ``*.npy`` files in ``input_folder``."""
        self._interact_with_folder(input_folder, 'r')

    def export(self, output_folder):
        """Export matrices as ``*.npy`` files to an output folder."""
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        self._interact_with_folder(output_folder, 'w')

    def rectify(self, frames):
        """
        Rectify frames passed as (left, right) pair of OpenCV Mats.

        Remapping is done with nearest neighbor for speed.
        """
        new_frames = []
        for i, side in enumerate(("left", "right")):
            new_frames.append(cv2.remap(frames[i],
                                        self.undistortion_map[side],
                                        self.rectification_map[side],
                                        cv2.INTER_NEAREST))
        return new_frames


class StereoCalibrator(object):

    """A class that calibrates stereo cameras by finding chessboard corners."""

    def _get_corners(self, image):
        """Find subpixel chessboard corners in image."""
        temp = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        ret, corners = cv2.findChessboardCorners(temp,
                                                 (self.rows, self.columns))
        if not ret:
            raise Exception("No chessboard could be found.")
        cv2.cornerSubPix(temp, corners, (11, 11), (-1, -1),
                         (cv2.TERM_CRITERIA_MAX_ITER + cv2.TERM_CRITERIA_EPS,
                          30, 0.01))
        return corners

    def _show_corners(self, image, corners):
        """Show chessboard corners found in image."""
        temp = image
        cv2.drawChessboardCorners(temp, (self.rows, self.columns), corners,
                                  True)
        window_name = "Chessboard"
        cv2.imshow(window_name, temp)
        if cv2.waitKey(0):
            cv2.destroyWindow(window_name)
            
    def _draw_corners(self, image, corners, img_side):
        
        cv2.drawChessboardCorners(image, (self.rows, self.columns), corners, True)
        cv2.imwrite(os.path.join(self.out_dir, str(self.save_ind)+'_'+img_side+'.jpg'), image)

    def __init__(self, rows, columns, square_size, image_size):
        """
        Store variables relevant to the camera calibration.

        ``corner_coordinates`` are generated by creating an array of 3D
        coordinates that correspond to the actual positions of the chessboard
        corners observed on a 2D plane in 3D space.
        """
        #: Number of calibration images
        self.image_count = 0
        #: Number of inside corners in the chessboard's rows
        self.rows = rows
        #: Number of inside corners in the chessboard's columns
        self.columns = columns
        #: Size of chessboard squares in cm
        self.square_size = square_size
        #: Size of calibration images in pixels
        self.image_size = image_size
        pattern_size = (self.rows, self.columns)
        corner_coordinates = np.zeros((np.prod(pattern_size), 3), np.float32)
        corner_coordinates[:, :2] = np.indices(pattern_size).T.reshape(-1, 2)
        corner_coordinates *= self.square_size
        #: Real world corner coordinates found in each image
        self.corner_coordinates = corner_coordinates
        #: Array of real world corner coordinates to match the corners found
        self.object_points = []
        #: Array of found corner coordinates from calibration images for left
        #: and right camera, respectively
        self.image_points = {"left": [], "right": []}
        
        #: draw corners in image
        self.save_ind = 0
        self.out_dir = '/Users/nijiang/Desktop/pythonTest/stereoTop/calibResult/draw_corners'

    def add_corners(self, image_pair, show_results=False):
        """
        Record chessboard corners found in an image pair.

        The image pair should be an iterable composed of two CvMats ordered
        (left, right).
        """
        left_corners = self._get_corners(image_pair[0])
        right_corners = self._get_corners(image_pair[1])
        
        self.image_points["left"].append(left_corners.reshape(-1, 2))
        self.image_points["right"].append(right_corners.reshape(-1, 2))
        self.image_count += 2
        self.object_points.append(self.corner_coordinates)
        if show_results:
            self._draw_corners(image_pair[0], left_corners, 'left')
            self._draw_corners(image_pair[1], right_corners, 'right')
            self.save_ind += 1
        
        '''
        side = "left"
        for image in image_pair:
            corners = self._get_corners(image)
            if show_results:
                self._show_corners(image, corners)
            self.image_points[side].append(corners.reshape(-1, 2))
            side = "right"
            self.image_count += 1
        self.object_points.append(self.corner_coordinates)
        '''

    def calibrate_cameras(self):
        """Calibrate cameras based on found chessboard corners."""
        criteria = (cv2.TERM_CRITERIA_MAX_ITER + cv2.TERM_CRITERIA_EPS,
                    100, 1e-5)
        stereo_flag = (cv2.CALIB_FIX_INTRINSIC+cv2.CALIB_FIX_ASPECT_RATIO + cv2.CALIB_FIX_FOCAL_LENGTH
                +cv2.CALIB_FIX_PRINCIPAL_POINT)
        #stereo_flag = cv2.CALIB_USE_INTRINSIC_GUESS
        calib = StereoCalibration()
        '''
        calib.cam_mats["left"] = []
        calib.cam_mats["right"] = []
        calib.cam_mats["left"].append(np.array([6761, 0, 0]).astype('float'))
        calib.cam_mats["left"].append(np.array([0, 6700, 0]).astype('float'))
        calib.cam_mats["left"].append(np.array([1818, 1007, 1]).astype('float'))
        
        calib.cam_mats["right"].append(np.array([6888, 0, 0]).astype('float'))
        calib.cam_mats["right"].append(np.array([0, 6821, 0]).astype('float'))
        calib.cam_mats["right"].append(np.array([1664, 1096, 1]).astype('float'))
        '''
        calib.cam_mats['left'] = np.zeros((3,3))
        calib.cam_mats['left'][0,0] = 6761
        calib.cam_mats['left'][0,1] = 0
        calib.cam_mats['left'][0,2] = 0
        calib.cam_mats['left'][1,0] = 0
        calib.cam_mats['left'][1,1] = 6700
        calib.cam_mats['left'][1,2] = 0
        calib.cam_mats['left'][2,0] = 1818
        calib.cam_mats['left'][2,1] = 1007
        calib.cam_mats['left'][2,2] = 1
        calib.cam_mats['right'] = np.zeros((3,3))
        calib.cam_mats['right'][0,0] = 6888
        calib.cam_mats['right'][0,1] = 0
        calib.cam_mats['right'][0,2] = 0
        calib.cam_mats['right'][1,0] = 0
        calib.cam_mats['right'][1,1] = 6821
        calib.cam_mats['right'][1,2] = 0
        calib.cam_mats['right'][2,0] = 1664
        calib.cam_mats['right'][2,1] = 1096
        calib.cam_mats['right'][2,2] = 1

        
        (calib.cam_mats["left"], calib.dist_coefs["left"],
         calib.cam_mats["right"], calib.dist_coefs["right"],
         calib.rot_mat, calib.trans_vec, calib.e_mat,
         calib.f_mat) = cv2.stereoCalibrate(self.object_points,
                                            self.image_points["left"],
                                            self.image_points["right"],
                                            self.image_size,
                                            calib.cam_mats["left"],
                                            calib.dist_coefs["left"],
                                            calib.cam_mats["right"],
                                            calib.dist_coefs["right"],
                                            #self.image_size,
                                            calib.rot_mat,
                                            calib.trans_vec,
                                            calib.e_mat,
                                            calib.f_mat,
                                            criteria=criteria,
                                            flags=stereo_flag)[1:]
        (calib.rect_trans["left"], calib.rect_trans["right"],
         calib.proj_mats["left"], calib.proj_mats["right"],
         calib.disp_to_depth_mat, calib.valid_boxes["left"],
         calib.valid_boxes["right"]) = cv2.stereoRectify(calib.cam_mats["left"],
                                                      calib.dist_coefs["left"],
                                                      calib.cam_mats["right"],
                                                      calib.dist_coefs["right"],
                                                      self.image_size,
                                                      calib.rot_mat,
                                                      calib.trans_vec,
                                                      flags=0)
        for side in ("left", "right"):
            (calib.undistortion_map[side],
             calib.rectification_map[side]) = cv2.initUndistortRectifyMap(
                                                        calib.cam_mats[side],
                                                        calib.dist_coefs[side],
                                                        calib.rect_trans[side],
                                                        calib.proj_mats[side],
                                                        self.image_size,
                                                        cv2.CV_32FC1)
        '''
        # This is replaced because my results were always bad. Estimates are
        # taken from the OpenCV samples.
        width, height = self.image_size
        focal_length = 0.8 * width
        calib.disp_to_depth_mat = np.float32([[1, 0, 0, -0.5 * width],
                                              [0, -1, 0, 0.5 * height],
                                              [0, 0, 0, -focal_length],
                                              [0, 0, 1, 0]])
                                              '''
        return calib

    def check_calibration(self, calibration):
        """
        Check calibration quality by computing average reprojection error.

        First, undistort detected points and compute epilines for each side.
        Then compute the error between the computed epipolar lines and the
        position of the points detected on the other side for each point and
        return the average error.
        """
        sides = "left", "right"
        which_image = {sides[0]: 1, sides[1]: 2}
        undistorted, lines = {}, {}
        for side in sides:
            undistorted[side] = cv2.undistortPoints(
                         np.concatenate(self.image_points[side]).reshape(-1,
                                                                         1, 2),
                         calibration.cam_mats[side],
                         calibration.dist_coefs[side],
                         P=calibration.cam_mats[side])
            lines[side] = cv2.computeCorrespondEpilines(undistorted[side],
                                              which_image[side],
                                              calibration.f_mat)
        total_error = 0
        npoints = 0
        this_side, other_side = sides
        for side in sides:
            for i in range(len(undistorted[side])):
                single_error = abs(undistorted[this_side][i][0][0] *
                                   lines[other_side][i][0][0] +
                                   undistorted[this_side][i][0][1] *
                                   lines[other_side][i][0][1] +
                                   lines[other_side][i][0][2])
                
                if single_error > 20:
                    print('id:%d, error:%f\n' % (i, single_error))
                
                total_error += single_error
                npoints += 1
            other_side, this_side = sides
        print npoints
        return total_error / (npoints)
