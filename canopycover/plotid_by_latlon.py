# plotid_by_latlon.py: Query plot id by <lon, lat> point
# Yan Y. Liu <yanliu@illinois.edu>
# 01/26/2017
# Usage: python plotid_by_latlon.py shpfile lon lat
# Output: id of the plot which contains, touches, or is closest to the point. None if something wrong
# Dependency: GDAL 2.0+ with GEOS, PROJ4, and python library support
import sys, os, string, copy
from osgeo import gdal
from osgeo import ogr
from osgeo import osr

def plotQuery(shpFile = None, lon = 0, lat = 0):
    if not os.path.exists(shpFile):
        print "plotQuery(): ERROR shp file does not exist: " + str(shpFile)
        return None

    # open plot shp file
    ds = gdal.OpenEx( shpFile, gdal.OF_VECTOR | gdal.OF_READONLY)
    if ds is None :
        print "plotQuery(): ERROR Open failed: " + str(shpFile) + "\n"
        return None
    layerName = os.path.basename(shpFile).split('.shp')[0]
    lyr = ds.GetLayerByName( layerName )
    if lyr is None :
        print "plotQuery(): ERROR fetch layer: " + str(layerName) + "\n"
        return None

    # load shp file
    lyr.ResetReading()
    num_records = lyr.GetFeatureCount()
    lyr_defn = lyr.GetLayerDefn()
    t_srs = lyr.GetSpatialRef()

    # create point
    point = ogr.Geometry(ogr.wkbPoint)
    point.SetPoint_2D(0, lon, lat)
    s_srs = osr.SpatialReference()
    s_srs.ImportFromEPSG(4326)
    transform = osr.CoordinateTransformation(s_srs, t_srs)
    transform_back = osr.CoordinateTransformation(t_srs, s_srs)
    point.Transform(transform)

    fi_rangepass = lyr_defn.GetFieldIndex('RangePass')
    fi_range = lyr_defn.GetFieldIndex('Range')
    fi_pass = lyr_defn.GetFieldIndex('Pass')
    fi_macentry = lyr_defn.GetFieldIndex('MAC_ENTRY')

    min = 1000000000.0
    minid = None
    mingeom = None
    for f in lyr: # for each plot
        plotid = f.GetFieldAsString(fi_rangepass)
        rangeid = f.GetFieldAsInteger(fi_range)
        passid = f.GetFieldAsInteger(fi_pass)
        macentryid = f.GetFieldAsInteger(fi_macentry)
        geom = f.GetGeometryRef()
        if (geom.Contains(point) or geom.Touches(point)): # GDAL needs to support Covers() for better efficiency
            #print "plotQuery(): INFO point in plot"
            ds = None
            geom.Transform(transform_back)
            centroid = geom.Centroid()
            return {"plot":plotid, "geom":geom, "point": [centroid.GetY(), centroid.GetX(), 0]}
        # calc distance and update nearest
        d = geom.Distance(point)
        if (d < min):
            min = d
            minid = plotid
            mingeom = copy.copy(geom)

    ds = None
    if minid is None:
        print "plotQuery(): ERROR searched but couldn't find nearest plot. Check data file or the point. "
        return None
    #print "plotQuery(): INFO point not in plot"
    geom.Transform(transform_back)
    centroid = geom.Centroid()
    return {"plot":minid, "geom":mingeom, "point": [centroid.GetY(), centroid.GetX(), 0]}

# Example run:
# python plotid_by_latlon.py data/sorghumexpfall2016v5_lblentry_1to7.shp -111.97495668222 33.0760167027358
# plotQuery(): INFO point in plot
# 42-3
if __name__ == '__main__':
    shpFile = sys.argv[1] # shp file path
    lon = float(sys.argv[2]) # point lon
    lat = float(sys.argv[3]) # point lat
    print plotQuery(shpFile, lon, lat)