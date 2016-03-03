#!/usr/bin/env python

import os
import sys
import time
import platform
import argparse
from datetime import datetime
from space_checker_utils import wget_wrapper

import ConfigParser


class Installer(object):
    """
    This class takes care of installation of various restricted stuff across various linux distros
    """
    def __init__(self, RootDir):
        self.RootDir = RootDir
        self.pid = os.getpid()
        self.scripts_path = os.path.join(RootDir, "scripts") # custom scripts
        self.owtf_pip = os.path.join(RootDir, "install", "owtf.pip") # OWTF python libraries
        self.restricted_cfg = os.path.join(RootDir, "install", "distro-independent.cfg") # Restricted tools and dictionaries which are distro independent
        self.distros_cfg = os.path.join(RootDir, "install", "linux-distributions.cfg") # Various distros and install scripts
        self.parser = argparse.ArgumentParser()
        self.parser.add_argument('--no-user-input', help='run script with default options for user input', action="store_true")
        self.parser.add_argument('--core-only', help='install only owtf dependencies, skip optional tools', action="store_true")

    def create_directory(self, directory):
        # Create parent directories as necessary
        try:
            os.makedirs(directory)
            return True
        except OSError:
            # Checks if the folder is empty
            if not os.listdir(directory):
                return True
            return False

    def run_command(self, command):
        Colorizer.normal("[*] Running following command")
        Colorizer.info("%s" % command)
        if not wget_wrapper(command):
            return
        os.system(command)

    @staticmethod
    def version(root_dir):
        """Prints the local git repo's last commit hash"""
        # check if the root dir is a git repository
        if os.path.exists(os.path.join(root_dir, '.git')):
            command = 'git log -n 1 --pretty=format:"%H"'
            commit_hash = os.popen(command).read()
            return commit_hash
        else:
            return "*Not a git repository.*"

    @staticmethod
    def check_sudo():
        """Checks if the user has sudo access"""
        sudo = os.system("sudo -v")
        if sudo == 0:
            return
        else:
            Colorizer.warning("[!] Your user does not have sudo privileges. Some OWTF components require sudo permissions to install")
            # exit cleanly
            sys.exit()

    def install_in_directory(self, directory, command):
        if self.create_directory(directory):
            Colorizer.info("[*] Switching to %s" % directory)
            os.chdir(directory)
            self.run_command(command)
        else:
            Colorizer.warning("[!] Directory %s already exists, so skipping installation for this" % directory)

    def install_using_pip(self, requirements_file):
        # Instead of using file directly with pip which can crash because of single library
        self.run_command("sudo -E pip2 install --upgrade -r %s" % requirements_file)

    def install_restricted_from_cfg(self, config_file):
        cp = ConfigParser.ConfigParser({"RootDir":self.RootDir, "Pid":self.pid})
        cp.read(config_file)
        for section in cp.sections():
            Colorizer.info("[*] Installing %s" % section)
            self.install_in_directory(os.path.expanduser(cp.get(section, "directory")), cp.get(section, "command"))

    def install(self, cmd_arguments):

        args = self.parser.parse_args(cmd_arguments)

        # User asked to select distro (in case it cannot be automatically detected) and distro related stuff is installed
        cp = ConfigParser.ConfigParser({"RootDir":self.RootDir, "Pid":self.pid})
        cp.read(self.distros_cfg)

        #Try get the distro automatically
        distro, version, arch = platform.linux_distribution()
        distro_num = 0
        if "kali" in distro.lower():
            distro_num = 1
        elif "samurai" in distro.lower():
            distro_num = 2
        elif "debian" in distro.lower():
            distro_num = 3

        # Loop until proper input is received
        while True:
            if distro_num != 0:
                Colorizer.info("[*] %s has been automatically detected... " % distro)
                Colorizer.normal("Continuing in auto-mode")
                break

            if args.no_user_input:
                distro_num = 0
                break

            print("")
            for i, item in enumerate(cp.sections()):
                Colorizer.warning("(%d) %s" % (i + 1, item))
            Colorizer.warning("(0) My distro is not listed :( %s" % distro)

            distro_num = raw_input(Colorizer.normal("Select a number based on your distribution : "))
            try: # Cheking if valid input is received
                distro_num = int(distro_num)
                break
            except ValueError:
                print('')
                Colorizer.warning("Invalid Number specified")
                continue

        # First all distro independent stuff is installed
        self.install_restricted_from_cfg(self.restricted_cfg)

        if distro_num != 0:
            self.run_command(cp.get(cp.sections()[int(distro_num)-1], "install"))
        else:
            Colorizer.normal("Skipping distro related installation :(")

        if args.core_only:
            return

        Colorizer.normal("Upgrading pip to the latest version ...")
        # Upgrade pip before install required libraries
        self.run_command("sudo pip2 install --upgrade pip")
        # mitigate cffi errors by upgrading it first
        self.run_command("sudo pip2 install --upgrade cffi")
        # run next block only when distro_num == 1
        if distro_num == '1':
            # check kali major release number 0.x, 1.x, 2.x
            kali_version = os.popen("cat /etc/issue", "r").read().split(" ")[2][0]
            if kali_version == '1':
                if args.no_user_input:
                    fixsetuptools = 'n'
                else:
                    # ask the user if they really want to delete the symlink
                    fixsetuptools = raw_input("Delete /usr/lib/python2.7/dist-packages/setuptools.egg-info? (y/n)\n(recommended, solves some issues in Kali 1.xx)")

                if fixsetuptools == 'y':
                    # backup the original symlink
                    Colorizer.normal("Backing up the original symlink...")
                    ts = time.time()
                    human_timestamp = datetime.fromtimestamp(ts).strftime('%Y-%m-%d-%H:%M:%S')

                    # backup the original symlink
                    symlink_orig_path = "/usr/lib/python2.7/dist-packages/setuptools.egg-info"
                    self.run_command("mv %s %s-BACKUP-%s" % (symlink_orig_path, symlink_orig_path, human_timestamp))

                    Colorizer.info("The original symlink exists at %s-BACKUP-%s" % (symlink_orig_path, human_timestamp))

                    # Finally owtf python libraries installed using pip
                    self.install_using_pip(self.owtf_pip)
            else:
                Colorizer.warning("Moving on with the installation but you were warned: there may be some errors!")

        # Finally owtf python libraries installed using pip
        self.install_using_pip(self.owtf_pip)

        # db_setup script
        self.run_command("sudo sh %s init" % (os.path.join(self.scripts_path, "db_setup.sh")))
        # db_run script
        self.run_command("sudo sh %s" % (os.path.join(self.scripts_path, "db_run.sh")))


class Colorizer:

    """Helper class for colorized strings.

    Different statements will have different colors:

        - `normal`, denoting ongoing procedure (WHITE)
        - `info`, any file path, commit hash or any other info (BLUE)
        - `warning`, any potential hindrance in installation (YELLOW)
        - `danger`, abrupt failure, desired file/dir not found etc. (RED)
    """

    BOLD = '\033[1m'
    RED = BOLD + '\033[91m'
    GREEN = BOLD + '\033[92m'
    YELLOW = BOLD + '\033[93m'
    BLUE = BOLD + '\033[34m'
    PURPLE = BOLD + '\033[95m'
    CYAN = BOLD + '\033[36m'
    WHITE = BOLD + '\033[37m'
    END = '\033[0m\033[0m'

    def __init__(self):
        pass

    @classmethod
    def normal(cls, string):
        print(cls.WHITE + string + cls.END)

    @classmethod
    def info(cls, string):
        print(cls.CYAN + string + cls.END)

    @classmethod
    def warning(cls, string):
        print(cls.YELLOW + string + cls.END)

    @classmethod
    def success(cls, string):
        print(cls.GREEN + string + cls.END)

    @classmethod
    def danger(cls, string):
        print(cls.RED + string + cls.END)


if __name__ == "__main__":
    Colorizer.normal("[*] Great that you are installing OWTF :D")
    Colorizer.warning("[!] There will be lot of output, please be patient")

    RootDir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    installer = Installer(RootDir)
    Colorizer.info("[DEBUG] Last commit hash: %s" % installer.version(RootDir))
    installer.check_sudo()
    installer.install(sys.argv[1:])

    Colorizer.success("[*] Finished!")
    Colorizer.info("[*] Start OWTF by running './owtf.py' in parent directory")
