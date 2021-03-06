#from django.db import models
import os
import plistlib

from django.conf import settings

REPO_DIR = settings.MUNKI_REPO_DIR


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


class Catalog(object):
    @classmethod
    def list(self):
        '''Returns a list of available catalogs, which is a list
        of catalog names (strings)'''
        catalogs_path = os.path.join(REPO_DIR, 'catalogs')
        catalogs = []
        for name in os.listdir(catalogs_path):
            if name.startswith("._") or name == ".DS_Store" or name == 'all':
                # don't process these
                continue
            try:
                catalog = plistlib.readPlist(
                    os.path.join(catalogs_path, name))
            except Exception:
                # skip items that aren't valid plists
                pass
            else:
                catalogs.append(name)
        return catalogs
            
    
    @classmethod
    def detail(self, catalog_name):
        '''Gets the contents of a catalog, which is a list
        of pkginfo items'''
        catalog_path = os.path.join(
            REPO_DIR, 'catalogs', catalog_name)
        if os.path.exists(catalog_path):
            try:
                catalog_items = plistlib.readPlist(catalog_path)
                index = 0
                for item in catalog_items:
                    item['index'] = index
                    index += 1
                return catalog_items
            except Exception, errmsg:
                return None
        else:
            return None


    @classmethod
    def item_detail(self, catalog_name, item_index):
        '''Returns detail for a single catalog item'''
        catalog_path = os.path.join(
            REPO_DIR, 'catalogs', catalog_name)
        if os.path.exists(catalog_path):
            try:
                catalog_items = plistlib.readPlist(catalog_path)
                return catalog_items[int(item_index)]
            except Exception, errmsg:
                return None
        else:
            return None


    @classmethod
    def getValidInstallItems(self, catalog_list):
        '''Returns a list of valid install item names for the
        list of catalogs'''
        install_items = set()
        for catalog in catalog_list:
            catalog_items = Catalog.detail(catalog)
            catalog_item_names = list(set(
                [item['name'] for item in catalog_items]))
            install_items.update(catalog_item_names)
            catalog_item_names_with_versions = list(set(
                [item['name'] + '-' + trimVersionString(item['version'])
                 for item in catalog_items]))
            install_items.update(catalog_item_names_with_versions)
        return list(install_items)

    @classmethod
    def catalog_info(cls):
        '''Returns a dictionary containing types of install items
        used by autocomplete and manifest validation'''
        catalog_info = {}
        categories_set = set()
        developers_set = set()
        catalog_list = Catalog.list()
        for catalog in catalog_list:
            suggested_set = set()
            update_set = set()
            versioned_set = set()
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
                catalog_info[catalog] = {}
                catalog_info[catalog]['suggested'] = list(suggested_set)
                catalog_info[catalog]['updates'] = list(update_set)
                catalog_info[catalog]['with_version'] = list(versioned_set)
                categories_set.update(
                    {item['category'] for item in catalog_items
                     if item.get('category')})
                developers_set.update(
                    {item['developer'] for item in catalog_items
                     if item.get('developer')})
        catalog_info['_categories'] = list(categories_set)
        catalog_info['_developers'] = list(developers_set)
        return catalog_info
