'''
Created on Sep 6, 2016

@author: Zongyang Li
'''
import json, sys, utm
import numpy as np
from math import cos, pi
from terrautils.betydb import get_site_boundaries

# Scanalyzer -> MAC formular @ https://terraref.gitbooks.io/terraref-documentation/content/user/geospatial-information.html
# Mx = ax + bx * Gx + cx * Gy
# My = ay + by * Gx + cy * Gy
# Gx = ( (My/cy - ay/cy) - (Mx/cx - ax/cx) ) / (by/cy - bx/cx)
# Gy = ( (My/by - ay/by) - (Mx/bx - ax/bx) ) / (cy/by - cx/bx)
SE_latlon = (33.07451869,-111.97477775)
ay = 3659974.971; by = 1.0002; cy = 0.0078;
ax = 409012.2032; bx = 0.009; cx = - 0.9986;
SE_utm = utm.from_latlon(SE_latlon[0], SE_latlon[1])
lng_shift = 0.000020308287
lat_shift = 0.000015258894

"(latitude, longitude) of SE corner (positions are + in NW direction)"
ZERO_ZERO = (33.0745,-111.97475)

class CoordinateConverter(object):
    """
        This class implements coordinate conversions
        what coordinate system do we have in terra?
        LatLon, field_position, field_partition, plot_number, pixels
        
        LatLon: latitude/longitude, EPSG:4326, ZERO_ZERO = (33.0745,-111.97475)  SE corner (positions are + in NW direction)
        field_position: field position in meters which gantry system is using, ZERO_ZERO = (3.8, 0.0)
        field_partition: field are divided into 54 rows and 16 columns, partition(1, 1) is in SW corner (+ in NE direction)
        plot_number: a number that created by field_partition, details are in the file "Sorghum TERRA plot plan 2016 4.21.16.xlsx"
        pixels: (x,y,z) coordinate in different sensor data, 2-D or 3-D, need a parameter of 'field of view' or other parameter.
    """
    
    def __init__(self):
        self.fov = 0
        self.pixSize = 1
        self.x_range = 0
        self.y_column = 0
        self.seasonNum = 0
        self.np_bounds = np.zeros((54, 16, 4))
        self.np_bounds_subplot = np.zeros((54, 32, 4))
        self.useSubplot = False
        self.queryStatus = False
        self.plots = ''
    
    def fieldPosition_to_fieldPartition(self, x, y):
        
        plot_row = 0
        plot_col = 0
        if not self.queryStatus:
            return plot_row, plot_col
        
        if self.useSubplot:
            for i in range(54):
                xmin = self.np_bounds_subplot[i][0][0]
                xmax = self.np_bounds_subplot[i][0][1]
                if (x > xmin) and (x <= xmax):
                    plot_row = i + 1
                    break
                    
            for j in range(32):
                ymin = self.np_bounds_subplot[plot_row-1][j][2]
                ymax = self.np_bounds_subplot[plot_row-1][j][3]
                if (y > ymin) and (y <= ymax):
                    plot_col = j + 1
                    break
        else:
            for i in range(54):
                xmin = self.np_bounds[i][0][0]
                xmax = self.np_bounds[i][0][1]
                if (x > xmin) and (x <= xmax):
                    plot_row = i + 1
                    break
                    
            for j in range(16):
                ymin = self.np_bounds[plot_row-1][j][2]
                ymax = self.np_bounds[plot_row-1][j][3]
                if (y > ymin) and (y <= ymax):
                    plot_col = j + 1
                    break
        
        return plot_row, plot_col
    
    
    def plotNum_to_fieldPartition(self, plotNum):
        "Converts plot number to field partition"
        plot_row = 0
        plot_col = 0
        if not self.queryStatus:
            return plot_row, plot_col
        
        if not self.useSubplot:
            cols = 16
            col = plotNum % cols
            if col == 0:
                plot_row = plotNum / cols
                if (plot_row % 2 == 0):
                    plot_col = 1
                else:
                    plot_col = 16
                    
                return plot_row, plot_col
            
            
            plot_row = plotNum/cols +1
            plot_col = col
            if (plot_row % 2 == 0):
                plot_col = cols - col + 1
            
            return plot_row, plot_col
        else:
            cols = 32
            col = plotNum % cols
            if col == 0:
                plot_row = plotNum / cols
                if (plot_row % 2 == 0):
                    plot_col = 1
                else:
                    plot_col = 32
                    
                return plot_row, plot_col
            
            
            plot_row = plotNum/cols +1
            plot_col = col
            if (plot_row % 2 == 0):
                plot_col = cols - col + 1
            
            return plot_row, plot_col
    
    def pixel_to_plotNum(self, x, y, position, fov, scan_d, x_width, y_width):
        "Converts pixel to plot number, given pixel x, y, field position, sensor field of view, scan distance, image width and height"
        
        plotNum = 0
        if not self.queryStatus:
            return plotNum
        
        x_param = float(fov) / float(x_width)
        y_param = float(scan_d) / float(y_width)
        
        x_shift = x * x_param
        y_shift = y * y_param
        
        x_real = position[0] - float(fov)/2 + x_shift
        y_real = position[1] + y_shift
            
        plot_row, plot_col = self.fieldPosition_to_fieldPartition(x_real, y_real)
            
        plotNum = self.fieldPartition_to_plotNum(plot_row, plot_col)
        
        return plotNum
    
    def fieldPartition_to_plotNum(self, plot_row, plot_col):
        "Converts field partition to plot number"
        
        plotNum = 0
        if not self.queryStatus:
            return plotNum
        
        if self.useSubplot:
            return self.fieldPartition_to_plotNum_32(plot_row, plot_col)
        else:
            if plot_row == 0:
                return 0
            
            if plot_row % 2 == 0:
                plot_col = 17 - plot_col
                
            plotNum = (plot_row-1)*16 + plot_col
        
            return plotNum
    
    def fieldPartition_to_plotNum_32(self, plot_row, plot_col):
        "Converts field partition to plot number"
        if plot_row == 0:
            return 0
        
        if plot_row % 2 == 0:
            plot_col = 33 - plot_col
            
        plotNum = (plot_row-1)*32 + plot_col
    
        return plotNum
    
    
    def epsg_to_mac(self, latlng):
        
        Utm_lng = latlng[0] - lng_shift
        Utm_lat = latlng[1] + lat_shift
        
        mac = utm.from_latlon(Utm_lat, Utm_lng)
        
        return mac
    
    def mac_to_Scanalyzer(self, mac):
        # Gx = ( (My/cy - ay/cy) - (Mx/cx - ax/cx) ) / (by/cy - bx/cx)
        # Gy = ( (My/by - ay/by) - (Mx/bx - ax/bx) ) / (cy/by - cx/bx)
        Mx = mac[0]
        My = mac[1]
        
        Gx = ( (My/cy - ay/cy) - (Mx/cx - ax/cx) ) / (by/cy - bx/cx)
        Gy = ( (My/by - ay/by) - (Mx/bx - ax/bx) ) / (cy/by - cx/bx)
        
        return [Gx, Gy]
    
    def latlng_to_Scanalyzer(self, latlng):
        
        mac = self.epsg_to_mac(latlng)
        gantry_coord = self.mac_to_Scanalyzer(mac)
        
        return gantry_coord
    
    def bety_query(self, str_date, useSubplot=False):
        
        self.useSubplot = useSubplot
        
        self.plots = get_site_boundaries(str_date, city="Maricopa")
        
        self.parse_bety_plots()
        
        if self.useSubplot:
            records_num = np.count_nonzero(self.np_bounds_subplot)
            if records_num != 1728*4:
                self.queryStatus = False
                return False
        else:
            records_num = np.count_nonzero(self.np_bounds)
            if records_num != 864*4:
                self.queryStatus = False
                return False
        
        self.queryStatus = True
        return True
    
    def parse_bety_plots(self):
        
        for item in self.plots:
            if self.useSubplot:
                range_, col, xmin, xmax, ymin, ymax = self.parse_bety_sub_boundaries(item, self.plots[item])
            else:
                range_, col, xmin, xmax, ymin, ymax = self.parse_site_boundary(item, self.plots[item])
            if range_ == 0:
                continue
            self.insert_boundary_to_nparray(range_, col, xmin, xmax, ymin, ymax)
        
        return
    
    def parse_bety_sub_boundaries(self, site, bound_record):
        
        side_flag = -1
        
        if site.endswith(' E'):
            side_flag = 2
        elif site.endswith(' W'):
            side_flag = 1
        else:
            return 0, 0, 0, 0, 0, 0
        
        # MAC Field Scanner Season 4 Range 5 Column 6 W
        plot_record = [int(s) for s in site.split() if s.isdigit()]
        if len(plot_record) != 3:
            return 0, 0, 0, 0, 0, 0
        
        self.seasonNum = plot_record[0]
        range_ = plot_record[1]
        col = (plot_record[2]-1)*2 + side_flag
        
        latlngs = self.bety_str_parsing(bound_record)
        
        gantry_coords = []
        for latlng in latlngs:
            gantry_coords.append(self.latlng_to_Scanalyzer(latlng))
            
        xmin = gantry_coords[2][0]
        xmax = gantry_coords[0][0]
        ymin = gantry_coords[1][1]
        ymax = gantry_coords[0][1]
        
        return range_, col, xmin, xmax, ymin, ymax
    
    def parse_site_boundary(self, site, bound_record):
        
        # MAC Field Scanner Season 4 Range 5 Column 6
        plot_record = [int(s) for s in site.split() if s.isdigit()]
        if len(plot_record) != 3:
            return 0, 0, 0, 0, 0, 0
        
        self.seasonNum = plot_record[0]
        range_ = plot_record[1]
        col = plot_record[2]
        
        latlngs = self.bety_str_parsing(bound_record)
        
        gantry_coords = []
        for latlng in latlngs:
            gantry_coords.append(self.latlng_to_Scanalyzer(latlng))
            
        xmin = gantry_coords[2][0]
        xmax = gantry_coords[0][0]
        ymin = gantry_coords[1][1]
        ymax = gantry_coords[0][1]
        
        return range_, col, xmin, xmax, ymin, ymax
    
    def bety_str_parsing(self, bety_str):
        
        j = json.loads(bety_str)
        latlngs = []
        for i in range(4):
            latlngs.append(j['coordinates'][0][0][i])
        
        return latlngs
    
    def insert_boundary_to_nparray(self, range_, col, xmin, xmax, ymin, ymax):
        
        range_ -= 1
        col -= 1
        
        if self.useSubplot:
            self.np_bounds_subplot[range_][col][0] = xmin
            self.np_bounds_subplot[range_][col][1] = xmax
            self.np_bounds_subplot[range_][col][2] = ymin
            self.np_bounds_subplot[range_][col][3] = ymax
        else:
            self.np_bounds[range_][col][0] = xmin
            self.np_bounds[range_][col][1] = xmax
            self.np_bounds[range_][col][2] = ymin
            self.np_bounds[range_][col][3] = ymax
        
        return
    
    def getPlotNumForPixel(self, center_position, fov, imgSize):
        
        plotNum = []
        pixelBoundary = []
        if not self.queryStatus or not self.useSubplot:
            return plotNum, pixelBoundary
        
        fov_ew = fov[1]
        center_ew = center_position[1]
        start_boundary = 0
        start_point = center_ew + fov_ew/2
        
        start_range, start_col = self.fieldPosition_to_fieldPartition(center_position[0], start_point)
        
        for i in range(3):
            cur_row = start_range
            cur_col = start_col
            if cur_row > 53 or cur_col > 31 or cur_col < 0:
                break
            
            cur_plotNum = self.fieldPartition_to_plotNum(cur_row, cur_col)
            y_length = start_point - self.np_bounds_subplot[cur_row-1][cur_col-1][2]
            end_boundary = start_boundary + int(y_length/fov_ew*imgSize[1])
            if end_boundary > imgSize[1]:
                end_boundary = imgSize[1]
            
            plotNum.append(cur_plotNum)
            pixelBoundary.append([start_boundary, end_boundary])
            
            if end_boundary == imgSize[1]:
                break
            
            start_point = self.np_bounds_subplot[cur_row-1][cur_col-1][2]
            start_boundary = end_boundary
            start_range = cur_row
            start_col = cur_col + 1
            
        return plotNum, pixelBoundary
    

def load_json(meta_path):
    try:
        with open(meta_path, 'r') as fin:
            return json.load(fin)
    except Exception as ex:
        fail('Corrupt metadata file, ' + str(ex))
        
def fail(reason):
    print >> sys.stderr, reason
    
    
def lower_keys(in_dict):
    if type(in_dict) is dict:
        out_dict = {}
        for key, item in in_dict.items():
            out_dict[key.lower()] = lower_keys(item)
        return out_dict
    elif type(in_dict) is list:
        return [lower_keys(obj) for obj in in_dict]
    else:
        return in_dict