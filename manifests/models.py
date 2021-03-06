from django.db import models
import os
import subprocess
import plistlib
from catalogs.models import Catalog
from django.conf import settings
from process.utils import record_status
from munkiwebadmin.utils import MunkiGit

APPNAME = settings.APPNAME
REPO_DIR = settings.MUNKI_REPO_DIR
MANIFESTS_PATH = os.path.join(REPO_DIR, 'manifests')
MANIFESTS_PATH_PREFIX_LEN = len(MANIFESTS_PATH) + 1
MANIFEST_LIST_STATUS_TAG = 'manifest_list_process'

try:
    GIT = settings.GIT_PATH
except:
    GIT = None


def record(message=None, percent_done=None):
    record_status(
        MANIFEST_LIST_STATUS_TAG, message=message, percent_done=percent_done)


def trimVersionString(version_string):
    ### from munkilib.updatecheck
    """Trims all lone trailing zeros in the version string after major/minor.

    Examples:
      10.0.0.0 -> 10.0
      10.0.0.1 -> 10.0.0.1
      10.0.0-abc1 -> 10.0.0-abc1
      10.0.0-abc1.0 -> 10.0.0-abc1
    """
    if version_string == None or version_string == '':
        return ''
    version_parts = version_string.split('.')
    # strip off all trailing 0's in the version, while over 2 parts.
    while len(version_parts) > 2 and version_parts[-1] == '0':
        del(version_parts[-1])
    return '.'.join(version_parts)


class ManifestError(Exception):
    '''Class for Manifest errors'''
    pass


class ManifestReadError(ManifestError):
    '''Error reading a manifest'''
    pass


class ManifestWriteError(ManifestError):
    '''Error writing a manifest'''
    pass


class ManifestDeleteError(ManifestError):
    '''Error deleting a manifest'''
    pass


class ManifestDoesNotExistError(ManifestError):
    '''Error when manifest doesn't exist at pathname'''
    pass


class ManifestAlreadyExistsError(ManifestError):
    '''Error when creating a new manifest at an existing pathname'''
    pass


class ManifestFile(models.Model):
    '''Placeholder so we get permissions entries in the admin database'''
    pass


def manifest_names():
    '''Returns a list of manifest names'''
    manifests = []
    skipdirs = ['.svn', '.git', '.AppleDouble']
    for dirpath, dirnames, filenames in os.walk(MANIFESTS_PATH):
        record(message='Scanning %s' % dirpath[MANIFESTS_PATH_PREFIX_LEN:])
        for skipdir in skipdirs:
            if skipdir in dirnames:
                dirnames.remove(skipdir)
        subdir = dirpath[len(MANIFESTS_PATH):]
        manifests.extend([os.path.join(subdir, name).lstrip('/')
                         for name in filenames if not name.startswith('.')])
    return manifests


def read_manifest(pathname):
    '''Reads manifest at relative pathname. Returns a dict.'''
    manifest_path = os.path.join(REPO_DIR, 'manifests')
    filepath = os.path.join(manifest_path, pathname)
    try:
        return plistlib.readPlist(filepath)
    except:
        return None


class Manifest(object):

    @classmethod
    def list(cls):
        '''Returns a list of available manifests'''
        return manifest_names()

    @classmethod
    def new(cls, pathname, user):
        '''Returns a new empty manifest object'''
        manifest_path = os.path.join(REPO_DIR, 'manifests')
        filepath = os.path.join(manifest_path, pathname)
        if not os.path.exists(filepath):
            manifest = {}
            # create a useful empty manifest
            for section in [
                    'catalogs', 'included_manifests', 'managed_installs',
                    'managed_uninstalls', 'managed_updates',
                    'optional_installs']:
                manifest[section] = []
            data = plistlib.writePlistToString(manifest)
            try:
                with open(filepath, 'w') as FILEREF:
                    FILEREF.write(data.encode('utf-8'))
                print 'Wrote %s' % pathname
                if GIT:
                    MunkiGit().addFileAtPathForCommitter(filepath, user)
            except Exception, err:
                raise ManifestWriteError(err)
            return data
        else:
            raise ManifestAlreadyExistsError('File already exists!')

    @classmethod
    def read(cls, pathname):
        '''Reads a pkginfo file and returns the plist as text data'''
        manifest_path = os.path.join(REPO_DIR, 'manifests')
        filepath = os.path.join(manifest_path, pathname)
        if not os.path.exists(filepath):
            raise ManifestDoesNotExistError()
        default_items = {
            'catalogs': [],
            'included_manifests': [],
            'managed_installs': [],
            'managed_uninstalls': [],
            'managed_updates': [],
            'optional_installs': [],
        }
        try:
            plistdata = plistlib.readPlist(filepath)
            # define default fields for easier editing
            for item in default_items:
                if not item in plistdata:
                    plistdata[item] = default_items[item]
            return plistlib.writePlistToString(plistdata)
        except:
            # just read and return the raw text
            try:
                with open(filepath) as FILEREF:
                    pkginfo = FILEREF.read().decode('utf-8')
                return pkginfo
            except Exception, err:
                raise ManifestReadError(err)

    @classmethod
    def write(cls, data, pathname, user):
        '''Writes a manifest file'''
        manifest_path = os.path.join(REPO_DIR, 'manifests')
        filepath = os.path.join(manifest_path, pathname)
        try:
            with open(filepath, 'w') as FILEREF:
                FILEREF.write(data.encode('utf-8'))
            print 'Wrote %s' % pathname
            if GIT:
                MunkiGit().addFileAtPathForCommitter(filepath, user)
        except Exception, err:
            raise ManifestWriteError(err)

    @classmethod
    def delete(cls, pathname, user):
        '''Deletes a manifest file'''
        manifest_path = os.path.join(REPO_DIR, 'manifests')
        filepath = os.path.join(manifest_path, pathname)
        try:
            os.unlink(filepath)
            if GIT:
                MunkiGit().deleteFileAtPathForCommitter(filepath, user)
        except Exception, err:
            raise ManifestDeleteError(err)

    @classmethod
    def getInstallItemNames(cls, manifest_name):
        '''Returns a dictionary containing types of install items
        valid for the current manifest'''
        suggested_set = set()
        update_set = set()
        versioned_set = set()
        manifest = cls.read(manifest_name)
        if manifest:
            catalog_list = manifest.get('catalogs', ['all'])
            for catalog in catalog_list:
                catalog_items = Catalog.detail(catalog)
                if catalog_items:
                    suggested_names = list(set(
                        [item['name'] for item in catalog_items
                         if not item.get('update_for')]))
                    suggested_set.update(suggested_names)
                    update_names = list(set(
                        [item['name'] for item in catalog_items
                         if item.get('update_for')]))
                    update_set.update(update_names)
                    item_names_with_versions = list(set(
                        [item['name'] + '-' + 
                        trimVersionString(item['version'])
                        for item in catalog_items]))
                    versioned_set.update(item_names_with_versions)
        return {'suggested': list(suggested_set),
                'updates': list(update_set),
                'with_version': list(versioned_set)}


    @classmethod
    def findUserForManifest(cls, manifest_name):
        '''returns a username for a given manifest name'''
        if USERNAME_KEY:
            return cls.read(manifest_name).get(USERNAME_KEY, '')
