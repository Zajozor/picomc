import logging
import os
import shutil
import subprocess
import zipfile

import click

from picomc.globals import am, vm
from picomc.utils import PersistentObject, get_filepath, get_platform

logger = logging.getLogger('picomc.cli')

class NativesExtractor:
    def __init__(self, instance):
        self.instance = instance
        self.ndir = get_filepath('instances', instance.name, 'natives')

    def __enter__(self):
        version = self.instance.data['version']
        platform = get_platform()
        os.makedirs(self.ndir, exist_ok=True)
        for fullpath in vm.get_libs(version, natives=True):
            with zipfile.ZipFile(fullpath) as zf:
                zf.extractall(path=self.ndir)

    def __exit__(self, ext_type, exc_value, traceback):
        shutil.rmtree(self.ndir)
        #print(self.ndir)

def sanitize_name(name):
    return name.replace('..', '_').replace('/', '_')

class Instance(PersistentObject):
    data = {'version': 'latest'}
    def __init__(self, name):
        name = sanitize_name(name)
        self.CONFIG_FILE = os.path.join('instances', name, 'config.json')
        self.name = name

    def populate(self, version):
        self.data['version'] = version

    def launch(self, account):
        vm.prepare_version(self.data['version'])
        logger.info("Launching instance {}!".format(self.name))
        os.makedirs(get_filepath('instances', self.name,
                                 'minecraft'), exist_ok=True)
        with NativesExtractor(self):
            self._exec_mc(account)

    def _exec_mc(self, account):
        # this is temporary. FIXME
        vjson = vm.version_json(self.data['version'])
        version = vjson['id']
        java = '/usr/bin/java -Xmx1G'.split()
        libs = list(vm.get_libs(version))
        jarfile = get_filepath('versions', version, '{}.jar'.format(version))
        libs.append(jarfile)
        natives = get_filepath('instances', self.name, 'natives')
        mc = vjson['mainClass']
        gamedir = get_filepath('instances', self.name, 'minecraft')
        mcargs = vjson['minecraftArguments']
        mcargs = mcargs.replace("${","{")
        mcargs = mcargs.format(auth_player_name=account.username,
                      version_name=version,
                      game_directory=gamedir,
                      assets_root=get_filepath('assets'),
                      assets_index_name=vjson['assetIndex']['id'],
                      auth_uuid=account.get_uuid(),
                      auth_access_token=account.get_access_token(),
                      user_type='mojang',
                      version_type='picomc'
                      )
        fargs = java + [
            "-Djava.library.path={}".format(natives), '-cp', ':'.join(libs),
            mc, *mcargs.split(' ')]
        P = subprocess.run(fargs, cwd=gamedir)

    @classmethod
    def exists(cls, name):
        return os.path.exists(get_filepath('instances', name))


@click.group()
def instance_cli():
    """Manage your instances."""
    pass

@instance_cli.command()
@click.argument('name')
@click.option('--version', default='latest')
def create(name, version):
    if Instance.exists(name):
        logger.error("An instance with that name already exists.")
        return
    with Instance(name) as I:
        I.populate(version)

@instance_cli.command()
@click.argument('name')
@click.option('--account', default=None)
def launch(name, account):
    if account == None:
        account = am.get_default()
    else:
        account = am.get(account)
    if not Instance.exists(name):
        logger.error("No such instance exists.")
        return
    with Instance(name) as I:
        I.launch(account)
