#!/usr/bin/env python
# -*- coding: utf-8 -*-
###############################################################################
# $Id$
#
# Project:  GDAL/OGR Test Suite
# Purpose:  Test read functionality for HDF5 driver.
# Author:   Even Rouault <even dot rouault at mines dash paris dot org>
#
###############################################################################
# Copyright (c) 2008-2013, Even Rouault <even dot rouault at mines-paris dot org>
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
###############################################################################

import shutil

import pytest

from osgeo import gdal


import gdaltest

from uffd import uffd_compare

###############################################################################
# Test if HDF5 driver is present


pytestmark = pytest.mark.require_driver('HDF5')


@pytest.fixture(autouse=True)
def check_no_file_leaks():
    num_files = len(gdaltest.get_opened_files())

    yield

    diff = len(gdaltest.get_opened_files()) - num_files
    assert diff == 0, 'Leak of file handles: %d leaked' % diff


###############################################################################
# Confirm expected subdataset information.


def test_hdf5_2():
    ds = gdal.Open('data/groups.h5')

    sds_list = ds.GetMetadata('SUBDATASETS')

    assert len(sds_list) == 4, 'Did not get expected subdataset count.'

    assert sds_list['SUBDATASET_1_NAME'] == 'HDF5:"data/groups.h5"://MyGroup/Group_A/dset2' and sds_list['SUBDATASET_2_NAME'] == 'HDF5:"data/groups.h5"://MyGroup/dset1', \
        'did not get expected subdatasets.'

    ds = None

    assert not gdaltest.is_file_open('data/groups.h5'), 'file still opened.'

###############################################################################
# Confirm that single variable files can be accessed directly without
# subdataset stuff.


def test_hdf5_3():

    ds = gdal.Open('HDF5:"data/u8be.h5"://TestArray')

    cs = ds.GetRasterBand(1).Checksum()
    assert cs == 135, 'did not get expected checksum'

    ds = None

    assert not gdaltest.is_file_open('data/u8be.h5'), 'file still opened.'

###############################################################################
# Confirm subdataset access, and checksum.


def test_hdf5_4():

    ds = gdal.Open('HDF5:"data/u8be.h5"://TestArray')

    cs = ds.GetRasterBand(1).Checksum()
    assert cs == 135, 'did not get expected checksum'

###############################################################################
# Similar check on a 16bit dataset.


def test_hdf5_5():

    ds = gdal.Open('HDF5:"data/groups.h5"://MyGroup/dset1')

    cs = ds.GetRasterBand(1).Checksum()
    assert cs == 18, 'did not get expected checksum'

###############################################################################
# Test generating an overview on a subdataset.


def test_hdf5_6():

    shutil.copyfile('data/groups.h5', 'tmp/groups.h5')

    ds = gdal.Open('HDF5:"tmp/groups.h5"://MyGroup/dset1')
    ds.BuildOverviews(overviewlist=[2])
    ds = None

    assert not gdaltest.is_file_open('tmp/groups.h5'), 'file still opened.'

    ds = gdal.Open('HDF5:"tmp/groups.h5"://MyGroup/dset1')
    assert ds.GetRasterBand(1).GetOverviewCount() == 1, 'failed to find overview'
    ds = None

    # confirm that it works with a different path. (#3290)

    ds = gdal.Open('HDF5:"data/../tmp/groups.h5"://MyGroup/dset1')
    assert ds.GetRasterBand(1).GetOverviewCount() == 1, \
        'failed to find overview with alternate path'
    ovfile = ds.GetMetadataItem('OVERVIEW_FILE', 'OVERVIEWS')
    assert ovfile[:11] == 'data/../tmp', 'did not get expected OVERVIEW_FILE.'
    ds = None

    gdaltest.clean_tmp()

###############################################################################
# Coarse metadata check (regression test for #2412).


def test_hdf5_7():

    ds = gdal.Open('data/metadata.h5')
    metadata = ds.GetMetadata()
    metadataList = ds.GetMetadata_List()
    ds = None

    assert not gdaltest.is_file_open('data/metadata.h5'), 'file still opened.'

    assert len(metadata) == len(metadataList), 'error in metadata dictionary setup'

    metadataList = [item.split('=', 1)[0] for item in metadataList]
    for key in metadataList:
        try:
            metadata.pop(key)
        except KeyError:
            pytest.fail('unable to find "%s" key' % key)
    
###############################################################################
# Test metadata names.


def test_hdf5_8():

    ds = gdal.Open('data/metadata.h5')
    metadata = ds.GetMetadata()
    ds = None

    assert metadata, 'no metadata found'

    h5groups = ['G1', 'Group with spaces', 'Group_with_underscores',
                'Group with spaces_and_underscores']
    h5datasets = ['D1', 'Dataset with spaces', 'Dataset_with_underscores',
                  'Dataset with spaces_and_underscores']
    attributes = {
        'attribute': 'value',
        'attribute with spaces': 0,
        'attribute_with underscores': 0,
        'attribute with spaces_and_underscores': .1,
    }

    def scanMetadata(parts):
        for attr in attributes:
            name = '_'.join(parts + [attr])
            name = name.replace(' ', '_')
            assert name in metadata, ('unable to find metadata: "%s"' % name)

            value = metadata.pop(name)

            value = value.strip(' d')
            value = type(attributes[attr])(value)
            assert value == attributes[attr], ('incorrect metadata value for "%s": '
                                     '"%s" != "%s"' % (name, value,
                                                       attributes[attr]))

    # level0
    assert scanMetadata([]) is None

    # level1 datasets
    for h5dataset in h5datasets:
        assert scanMetadata([h5dataset]) is None

    # level1 groups
    for h5group in h5groups:
        assert scanMetadata([h5group]) is None

        # level2 datasets
        for h5dataset in h5datasets:
            assert scanMetadata([h5group, h5dataset]) is None

    
###############################################################################
# Variable length string metadata check (regression test for #4228).


def test_hdf5_9():

    if int(gdal.VersionInfo('VERSION_NUM')) < 1900:
        pytest.skip('would crash')

    ds = gdal.Open('data/vlstr_metadata.h5')
    metadata = ds.GetRasterBand(1).GetMetadata()
    ds = None
    assert not gdaltest.is_file_open('data/vlstr_metadata.h5'), 'file still opened.'

    ref_metadata = {
        'TEST_BANDNAMES': 'SAA',
        'TEST_CODING': '0.6666666667 0.0000000000 TRUE',
        'TEST_FLAGS': '255=noValue',
        'TEST_MAPPING': 'Geographic Lat/Lon 0.5000000000 0.5000000000 27.3154761905 -5.0833333333 0.0029761905 0.0029761905 WGS84 Degrees',
        'TEST_NOVALUE': '255',
        'TEST_RANGE': '0 255 0 255',
    }

    assert len(metadata) == len(ref_metadata), ('incorrect number of metadata: '
                             'expected %d, got %d' % (len(ref_metadata),
                                                      len(metadata)))

    for key in metadata:
        assert key in ref_metadata, ('unexpected metadata key "%s"' % key)

        assert metadata[key] == ref_metadata[key], \
            ('incorrect metadata value for key "%s": '
                                 'expected "%s", got "%s" ' %
                                 (key, ref_metadata[key], metadata[key]))

    
###############################################################################
# Test CSK_DGM.h5 (#4160)


def test_hdf5_10():

    # Try opening the QLK subdataset to check that no error is generated
    gdal.ErrorReset()
    ds = gdal.Open('HDF5:"data/CSK_DGM.h5"://S01/QLK')
    assert ds is not None and gdal.GetLastErrorMsg() == ''
    ds = None

    ds = gdal.Open('HDF5:"data/CSK_DGM.h5"://S01/SBI')
    got_gcpprojection = ds.GetGCPProjection()
    assert got_gcpprojection.startswith('GEOGCS["WGS 84",DATUM["WGS_1984"')

    got_gcps = ds.GetGCPs()
    assert len(got_gcps) == 4

    assert (abs(got_gcps[0].GCPPixel - 0) <= 1e-5 and abs(got_gcps[0].GCPLine - 0) <= 1e-5 and \
       abs(got_gcps[0].GCPX - 12.2395902509238) <= 1e-5 and abs(got_gcps[0].GCPY - 44.7280047434954) <= 1e-5)

    ds = None
    assert not gdaltest.is_file_open('data/CSK_DGM.h5'), 'file still opened.'

###############################################################################
# Test CSK_GEC.h5 (#4160)


def test_hdf5_11():

    # Try opening the QLK subdataset to check that no error is generated
    gdal.ErrorReset()
    ds = gdal.Open('HDF5:"data/CSK_GEC.h5"://S01/QLK')
    assert ds is not None and gdal.GetLastErrorMsg() == ''
    ds = None

    ds = gdal.Open('HDF5:"data/CSK_GEC.h5"://S01/SBI')
    got_projection = ds.GetProjection()
    assert got_projection.startswith('PROJCS["Transverse_Mercator",GEOGCS["WGS 84",DATUM["WGS_1984"')

    got_gt = ds.GetGeoTransform()
    expected_gt = (275592.5, 2.5, 0.0, 4998152.5, 0.0, -2.5)
    for i in range(6):
        assert abs(got_gt[i] - expected_gt[i]) <= 1e-5

    ds = None

    assert not gdaltest.is_file_open('data/CSK_GEC.h5'), 'file still opened.'

###############################################################################
# Test ODIM_H5 (#5032)


def test_hdf5_12():

    if not gdaltest.download_file('http://trac.osgeo.org/gdal/raw-attachment/ticket/5032/norsa.ss.ppi-00.5-dbz.aeqd-1000.20070601T000039Z.hdf', 'norsa.ss.ppi-00.5-dbz.aeqd-1000.20070601T000039Z.hdf'):
        pytest.skip()

    ds = gdal.Open('tmp/cache/norsa.ss.ppi-00.5-dbz.aeqd-1000.20070601T000039Z.hdf')
    got_projection = ds.GetProjection()
    assert 'Azimuthal_Equidistant' in got_projection

    got_gt = ds.GetGeoTransform()
    expected_gt = (-240890.02470187756, 1001.7181388478905, 0.0, 239638.21326987055, 0.0, -1000.3790932482976)
    # Proj 4.9.3
    expected_gt2 = (-240889.94573659054, 1001.7178235672992, 0.0, 239638.28570609915, 0.0, -1000.3794089534567)

    assert (max([abs(got_gt[i] - expected_gt[i]) for i in range(6)]) <= 1e-5 or \
       max([abs(got_gt[i] - expected_gt2[i]) for i in range(6)]) <= 1e-5)

###############################################################################
# Test MODIS L2 HDF5 GCPs (#6666)


def test_hdf5_13():

    if not gdaltest.download_file('http://oceandata.sci.gsfc.nasa.gov/cgi/getfile/A2016273115000.L2_LAC_OC.nc', 'A2016273115000.L2_LAC_OC.nc'):
        pytest.skip()

    ds = gdal.Open('HDF5:"tmp/cache/A2016273115000.L2_LAC_OC.nc"://geophysical_data/Kd_490')

    got_gcps = ds.GetGCPs()
    assert len(got_gcps) == 3030

    assert (abs(got_gcps[0].GCPPixel - 0.5) <= 1e-5 and abs(got_gcps[0].GCPLine - 0.5) <= 1e-5 and \
       abs(got_gcps[0].GCPX - 33.1655693) <= 1e-5 and abs(got_gcps[0].GCPY - 39.3207207) <= 1e-5)

###############################################################################
# Test complex data subsets


def test_hdf5_14():

    ds = gdal.Open('data/complex.h5')
    sds_list = ds.GetMetadata('SUBDATASETS')

    assert len(sds_list) == 6, 'Did not get expected complex subdataset count.'

    assert sds_list['SUBDATASET_1_NAME'] == 'HDF5:"data/complex.h5"://f16' and sds_list['SUBDATASET_2_NAME'] == 'HDF5:"data/complex.h5"://f32' and sds_list['SUBDATASET_3_NAME'] == 'HDF5:"data/complex.h5"://f64', \
        'did not get expected subdatasets.'

    ds = None

    assert not gdaltest.is_file_open('data/complex.h5'), 'file still opened.'

###############################################################################
# Confirm complex subset data access and checksum
# Start with Float32


def test_hdf5_15():

    ds = gdal.Open('HDF5:"data/complex.h5"://f32')

    cs = ds.GetRasterBand(1).Checksum()
    assert cs == 523, 'did not get expected checksum'

# Repeat for Float64


def test_hdf5_16():

    ds = gdal.Open('HDF5:"data/complex.h5"://f64')

    cs = ds.GetRasterBand(1).Checksum()
    assert cs == 511, 'did not get expected checksum'

# Repeat for Float16


def test_hdf5_17():

    ds = gdal.Open('HDF5:"data/complex.h5"://f16')

    cs = ds.GetRasterBand(1).Checksum()
    assert cs == 412, 'did not get expected checksum'


def test_hdf5_single_char_varname():

    ds = gdal.Open('HDF5:"data/single_char_varname.h5"://e')
    assert ds is not None


def test_hdf5_virtual_file():
    hdf5_files = [
        'CSK_GEC.h5',
        'vlstr_metadata.h5',
        'groups.h5',
        'complex.h5',
        'single_char_varname.h5',
        'CSK_DGM.h5',
        'u8be.h5',
        'metadata.h5'
    ]
    for hdf5_file in hdf5_files:
        assert uffd_compare(hdf5_file) is True

    

# FIXME: This FTP server seems to have disappeared. Replace with something else?
hdf5_list = [
    ('ftp://ftp.hdfgroup.uiuc.edu/pub/outgoing/hdf_files/hdf5/samples/convert', 'C1979091.h5',
        'HDF4_PALGROUP/HDF4_PALETTE_2', 7488, -1),
    ('ftp://ftp.hdfgroup.uiuc.edu/pub/outgoing/hdf_files/hdf5/samples/convert', 'C1979091.h5',
        'Raster_Image_#0', 3661, -1),
    ('ftp://ftp.hdfgroup.uiuc.edu/pub/outgoing/hdf_files/hdf5/geospatial/DEM', 'half_moon_bay.grid',
        'HDFEOS/GRIDS/DEMGRID/Data_Fields/Elevation', 30863, -1),
]


@pytest.mark.parametrize(
    'downloadURL,fileName,subdatasetname,checksum,download_size',
    hdf5_list,
    ids=['HDF5:"' + item[1] + '"://' + item[2] for item in hdf5_list],
)
def test_hdf5(downloadURL, fileName, subdatasetname, checksum, download_size):
    if not gdaltest.download_file(downloadURL + '/' + fileName, fileName, download_size):
        pytest.skip('no download')

    ds = gdal.Open('HDF5:"tmp/cache/' + fileName + '"://' + subdatasetname)

    assert ds.GetRasterBand(1).Checksum() == checksum, 'Bad checksum. Expected %d, got %d' % (checksum, ds.GetRasterBand(1).Checksum())




