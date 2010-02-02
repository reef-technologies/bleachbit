# vim: ts=4:sw=4:expandtab

## BleachBit
## Copyright (C) 2009 Andrew Ziem
## http://bleachbit.sourceforge.net
##
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program.  If not, see <http://www.gnu.org/licenses/>.



"""
Perform (or assist with) cleaning operations.
"""



import glob
try:
    import gtk
    HAVE_GTK = True
except:
    HAVE_GTK = False
import os.path
import re
import subprocess
import sys
import traceback

import Command
import FileUtilities
import Memory
import Special

if 'posix' == os.name:
    import Unix
elif 'nt' == os.name:
    import Windows

from Common import _
from FileUtilities import children_in_directory
from Options import options



class Cleaner:
    """Base class for a cleaner"""

    def __init__(self):
        self.actions = []
        self.id = None
        self.description = None
        self.name = None
        self.options = {}
        self.running = []
        self.warnings = {}

    def add_action(self, option_id, action):
        """Register 'action' (instance of class Action) to be executed
        for ''option_id'.  The actions must implement list_files and
        other_cleanup()"""
        self.actions += ( (option_id, action), )

    def add_option(self, option_id, name, description):
        """Register option (such as 'cache')"""
        self.options[option_id] = ( name, description )

    def add_running(self, detection_type, pathname):
        """Add a way to detect this program is currently running"""
        self.running += ( (detection_type, pathname), )

    def auto_hide(self):
        """Return boolean whether it is OK to automatically hide this
        cleaner"""
        for (option_id, __name) in self.get_options():
            try:
                for cmd in self.get_commands(option_id):
                    for ret in cmd.execute(False):
                        return False
                for ds in self.get_deep_scan(option_id):
                    if isinstance(ds, dict):
                        return False
            except:
                print 'warning: exception in auto_hide(), cleaner=%s, option=%s' % (self.name, option_id)
                traceback.print_exc()
        return True

    def get_commands(self, option_id):
        """Get list of Command instances for option 'option_id'"""
        for action in self.actions:
            if option_id == action[0]:
                for cmd in action[1].get_commands():
                    yield cmd
        if not self.options.has_key(option_id):
            raise RuntimeError("Unknown option '%s'" % option_id)

    def get_deep_scan(self, option_id):
        """Get dictionary used to build a deep scan"""
        for action in self.actions:
            if option_id == action[0]:
                for ds in action[1].get_deep_scan():
                    yield ds
        if not self.options.has_key(option_id):
            raise RuntimeError("Unknown option '%s'" % option_id)

    def get_description(self):
        """Brief description of the cleaner"""
        return self.description

    def get_id(self):
        """Return the unique name of this cleaner"""
        return self.id

    def get_name(self):
        """Return the human name of this cleaner"""
        return self.name

    def get_option_descriptions(self):
        """Yield the names and descriptions of each option in a 2-tuple"""
        if self.options:
            for key in sorted(self.options.keys()):
                yield ((self.options[key][0], self.options[key][1]))

    def get_options(self):
        """Return user-configurable options in 2-tuple (id, name)"""
        if self.options:
            for key in sorted(self.options.keys()):
                yield (key, self.options[key][0])


    def get_warning(self, option_id):
        """Return a warning as string."""
        if option_id in self.warnings:
            return self.warnings[option_id]
        else:
            return None

    def is_running(self):
        """Return whether the program is currently running"""
        for running in self.running:
            test = running[0]
            pathname = running[1]
            if 'exe' == test and 'posix' == os.name:
                if Unix.is_running(pathname):
                    print "debug: process '%s' is running" % pathname
                    return True
            elif 'exe' == test and 'nt' == os.name:
                print 'debug: type(%s) = %s' % (pathname, type(pathname))
                for p in Windows.enumerate_processes():
                    print 'debug: type(%s) = %s' % (p, type(p))
                    if p == pathname:
                        print "debug: process '%s' is running" % pathname
                        return True
            elif 'pathname' == test:
                expanded = os.path.expanduser(os.path.expandvars(pathname))
                for globbed in glob.iglob(expanded):
                    if os.path.exists(globbed):
                        print "debug: file '%s' exists indicating '%s' is running" % (globbed, self.name)
                        return True
            else:
                raise RuntimeError("Unknown running-detection test '%s'" % test)
        return False

    def is_usable(self):
        """Return whether the cleaner is usable (has actions)"""
        return len(self.actions) > 0

    def set_warning(self, option_id, description):
        """Set a warning to be displayed when option is selected interactively"""
        self.warnings[option_id] = description


class Firefox(Cleaner):
    """Mozilla Firefox"""

    def __init__(self):
        Cleaner.__init__(self)
        self.add_option('cache', _('Cache'), _('Delete the web cache, which reduces time to display revisited pages'))
        self.add_option('cookies', _('Cookies'), _('Delete cookies, which contain information such as web site preferences, authentication, and tracking identification'))
        self.add_option('download_history', _('Download history'), _('List of files downloaded'))
        self.add_option('forms', _('Form history'), _('A history of forms entered in web sites and in the Search bar'))
        self.add_option('session_restore', _('Session restore'), _('Loads the initial session after the browser closes or crashes'))
        self.add_option('passwords', _('Passwords'), _('A database of usernames and passwords as well as a list of sites that should not store passwords'))
        self.add_option('places', _('Places'), _('A database of URLs including bookmarks, favicons, and a history of visited web sites'))
        self.set_warning('places', _('This option deletes all bookmarks.'))
        self.add_option('url_history', _('URL history'), _('List of visited web pages'))
        self.add_option('vacuum', _('Vacuum'), _('Clean database fragmentation to reduce space and improve speed without removing any data'))

        if 'posix' == os.name:
            self.profile_dir = "~/.mozilla/firefox*/*/"
            self.add_running('exe', 'firefox')
            self.add_running('exe', 'firefox-bin')
            self.add_running('pathname', self.profile_dir + 'lock')
        elif 'nt' == os.name:
            self.profile_dir = "$USERPROFILE\\Application Data\\Mozilla\\Firefox\\Profiles\\*\\"
            self.add_running('exe', 'firefox.exe')
            self.add_running('pathname', self.profile_dir + 'parent.lock')

    def get_description(self):
        return _("Web browser")

    def get_id(self):
        return 'firefox'

    def get_name(self):
        return "Firefox"

    def get_commands(self, option_id):
        # browser cache
        cache_base = None
        if 'posix' == os.name:
            cache_base = self.profile_dir
        elif 'nt' == os.name:
            cache_base = "$USERPROFILE\\Local Settings\\Application Data\\Mozilla\\Firefox\\Profiles\\*"
        if 'cache' == option_id:
            dirs = FileUtilities.expand_glob_join(cache_base, "Cache*")
            dirs += FileUtilities.expand_glob_join(cache_base, "OfflineCache")
            for dirname in dirs:
                for filename in children_in_directory(dirname, False):
                    yield Command.Delete(filename)
        files = []
        # cookies
        if 'cookies' == option_id:
            files += FileUtilities.expand_glob_join(self.profile_dir, "cookies.txt")
            files += FileUtilities.expand_glob_join(self.profile_dir, "cookies.sqlite")
        # download history
        if 'download_history' == option_id:
            # Firefox version 1
            files += FileUtilities.expand_glob_join(self.profile_dir, "downloads.rdf")
            # Firefox version 3
            files += FileUtilities.expand_glob_join(self.profile_dir, "downloads.sqlite")
        # forms
        if 'forms' == option_id:
            files += FileUtilities.expand_glob_join(self.profile_dir, "formhistory.dat")
            files += FileUtilities.expand_glob_join(self.profile_dir, "formhistory.sqlite")
        # passwords
        if 'passwords' == option_id:
            files += FileUtilities.expand_glob_join(self.profile_dir, "signons.txt")
            files += FileUtilities.expand_glob_join(self.profile_dir, "signons[2-3].txt")
            files += FileUtilities.expand_glob_join(self.profile_dir, "signons.sqlite")
        # places database
        if 'places' == option_id:
            # Firefox version 3
            files += FileUtilities.expand_glob_join(self.profile_dir, "places.sqlite")
            files += FileUtilities.expand_glob_join(self.profile_dir, "places.sqlite-journal")
            files += FileUtilities.expand_glob_join(self.profile_dir, "bookmarkbackups/*ookmark*json")
            # see also option 'url_history'
        # session restore
        if 'session_restore' == option_id:
            files += FileUtilities.expand_glob_join(self.profile_dir, "sessionstore.js")
        # URL history
        if 'url_history' == option_id:
            # Firefox version 1
            files += FileUtilities.expand_glob_join(self.profile_dir, "history.dat")
            # see also function other_cleanup()
        # finish
        for filename in files:
            yield Command.Delete(filename)

        # URL history
        if 'url_history' == option_id:
            for path in FileUtilities.expand_glob_join(self.profile_dir, "places.sqlite"):
                yield Command.Function(path, \
                        Special.delete_mozilla_url_history,
                        _('Delete the usage history'))

        # vacuum
        if 'vacuum' == option_id:
            paths = []
            paths += FileUtilities.expand_glob_join(self.profile_dir, "*.sqlite")
            if not cache_base == self.profile_dir:
                paths += FileUtilities.expand_glob_join(cache_base, "*.sqlite")
            for path in paths:
                yield Command.Function(path, \
                    FileUtilities.vacuum_sqlite3, _("Vacuum"))



class OpenOfficeOrg(Cleaner):
    """Delete OpenOffice.org cache"""

    def __init__(self):
        Cleaner.__init__(self)
        self.options = {}
        self.add_option('cache', _('Cache'), _('Delete the cache'))
        self.add_option('recent_documents', _('Most recently used'), _("Delete the list of recently used documents"))

        # reference: http://katana.oooninja.com/w/editions_of_openoffice.org
        if 'posix' == os.name:
            self.prefixes = [ "~/.ooo-2.0", "~/.openoffice.org2", "~/.openoffice.org2.0", "~/.openoffice.org/3" ]
            self.prefixes += [ "~/.ooo-dev3" ]
        if 'nt' == os.name:
            self.prefixes = [ "$APPDATA\\OpenOffice.org\\3", "$APPDATA\\OpenOffice.org2" ]

    def get_description(self):
        return _("Office suite")

    def get_id(self):
        return 'openofficeorg'

    def get_name(self):
        return "OpenOffice.org"

    def get_commands(self, option_id):
        if 'recent_documents' == option_id:
            for prefix in self.prefixes:
                for path in FileUtilities.expand_glob_join(prefix, "user/registry/data/org/openoffice/Office/Histories.xcu"):
                    if os.path.lexists(path):
                        yield Command.Delete(path)
                for path in FileUtilities.expand_glob_join(prefix, "user/registry/cache/org.openoffice.Office.Histories.dat"):
                    if os.path.lexists(path):
                        yield Command.Delete(path)


        if 'recent_documents' == option_id and not 'cache' == option_id:
            for prefix in self.prefixes:
                for path in FileUtilities.expand_glob_join(prefix, "user/registry/cache/org.openoffice.Office.Common.dat"):
                    if os.path.lexists(path):
                        yield Command.Delete(path)

        if 'cache' == option_id:
            dirs = []
            for prefix in self.prefixes:
                dirs += FileUtilities.expand_glob_join(prefix, "user/registry/cache/")
            for dirname in dirs:
                for filename in children_in_directory(dirname, False):
                    yield Command.Delete(filename)


        if 'recent_documents' == option_id:
            for prefix in self.prefixes:
                for path in FileUtilities.expand_glob_join(prefix, "user/registry/data/org/openoffice/Office/Common.xcu"):
                    if os.path.lexists(path):
                        yield Command.Function(path, \
                            Special.delete_ooo_history,
                            _('Delete the usage history'))


class rpmbuild(Cleaner):
    """Delete the rpmbuild build directory"""

    def __init__(self):
        Cleaner.__init__(self)
        self.options = {}
        self.add_option('cache', _('Cache'), _('Delete the cache'))

    def get_description(self):
        return _("Delete the files in the rpmbuild build directory")

    def get_id(self):
        return 'rpmbuild'

    def get_name(self):
        return "rpmbuild"

    def get_commands(self, option_id):
        if not 'cache' == option_id:
            raise StopIteration

        dirnames = set([ os.path.expanduser("~/rpmbuild/BUILD/") ])
        try:
            args = ["rpm", "--eval", "%_topdir"]
            dirname = subprocess.Popen(args, stdout=subprocess.PIPE).\
                communicate()[0]
        except:
            print "warning: exception '%s' running '%s'" % \
                (str(sys.exc_info()[1]), " ".join(args))
        else:
            dirnames.add(dirname + "/BUILD")
        for dirname in dirnames:
            for filename in children_in_directory(dirname, True):
                yield Command.Delete(filename)


class System(Cleaner):
    """System in general"""

    def __init__(self):
        Cleaner.__init__(self)
        if 'posix' == os.name:
            # TRANSLATORS: desktop entries are .desktop files in Linux tha
            # make up the application menu (the menu that shows BleachBit,
            # Firefox, and others.  The .desktop files also associate file
            # types, so clicking on an .html file in Nautilus brings up
            # Firefox.
            # More information: http://standards.freedesktop.org/menu-spec/latest/index.html#introduction
            self.add_option('desktop_entry', _('Broken desktop files'), _('Delete broken application menu entries and file associations'))
            self.add_option('cache', _('Cache'), _('Delete the cache'))
            # TRANSLATORS: Localizations are files supporting specific
            # languages, so applications appear in Spanish, etc.
            self.add_option('localizations', _('Localizations'), _('Delete files for unwanted languages'))
            # TRANSLATORS: 'Rotated logs' refers to old system log files.
            # Linux systems often have a scheduled job to rotate the logs
            # which means compress all except the newest log and then delete
            # the oldest log.  You could translate this 'old logs.'
            self.add_option('rotated_logs', _('Rotated logs'), _('Delete old system logs'))
            self.add_option('recent_documents', _('Recent documents list'), _('Delete the list of recently used documents'))
            self.add_option('trash', _('Trash'), _('Empty the trash'))
        if 'linux2' == sys.platform:
            # TRANSLATORS: 'Free' is an adjective and could be translated
            # 'unallocated.'
            self.add_option('memory', _('Memory'), _('Wipe the swap and free memory'))
            self.set_warning('memory', _('This option is experimental and may cause system problems.'))
        if 'nt' == os.name:
            self.add_option('logs', _('Logs'), _('Delete the logs'))
            self.add_option('muicache', 'MUICache', _('Delete the cache'))
            # TRANSLATORS: Prefetch is Microsoft Windows jargon.
            self.add_option('prefetch', _('Prefetch'), _('Delete the cache'))
            self.add_option('recycle_bin', _('Recycle bin'), _('Empty the recycle bin'))
        if HAVE_GTK:
            self.add_option('clipboard', _('Clipboard'), _('The desktop environment\'s clipboard used for copy and paste operations'))
        self.add_option('free_disk_space', _('Free disk space'), _('Overwrite free disk space to hide deleted files'))
        self.set_warning('free_disk_space', _('This option is slow.'))
        self.add_option('tmp', _('Temporary files'), _('Delete the temporary files'))

    def get_description(self):
        return _("The system in general")

    def get_id(self):
        return 'system'

    def get_name(self):
        return _("System")

    def get_commands(self, option_id):
        # cache
        if 'posix' == os.name and 'cache' == option_id:
            dirname = os.path.expanduser("~/.cache/")
            for filename in children_in_directory(dirname, True):
                yield Command.Delete(filename)

        # menu
        menu_dirs = [ '~/.local/share/applications', \
            '~/.config/autostart', \
            '~/.gnome/apps/', \
            '~/.gnome2/panel2.d/default/launchers', \
            '~/.gnome2/vfolders/applications/', \
            '~/.kde/share/apps/RecentDocuments/', \
            '~/.kde/share/mimelnk', \
            '~/.kde/share/mimelnk/application/ram.desktop', \
            '~/.kde2/share/mimelnk/application/', \
            '~/.kde2/share/applnk' ]

        if 'posix' == os.name and 'desktop_entry' == option_id:
            for dirname in menu_dirs:
                for filename in [fn for fn in children_in_directory(dirname, False) \
                    if fn.endswith('.desktop') ]:
                    if Unix.is_broken_xdg_desktop(filename):
                        yield Command.Delete(filename)

        # unwanted locales
        if 'posix' == os.name and 'localizations' == option_id:
            callback = lambda locale, language: options.get_language(language)
            for path in Unix.locales.localization_paths(callback):
                yield Command.Delete(path)

        # Windows logs
        files = []
        if 'nt' == os.name and 'logs' == option_id:
            paths = ( \
                '$LocalAppData\\Microsoft\\Windows\\WER\\ReportArchive\\*\\*', \
                '$LocalAppData\\Microsoft\\Windows\WER\\ReportQueue\\*\\*', \
                '$programdata\\Microsoft\\Windows\\WER\\ReportArchive\\*\\*', \
                '$programdata\\Microsoft\\Windows\\WER\\ReportQueue\\*\\*', \
                '$userprofile\\Local Settings\\Application Data\\Microsoft\\Internet Explorer\\brndlog.bak', \
                '$userprofile\\Local Settings\\Application Data\\Microsoft\\Internet Explorer\\brndlog.txt', \
                '$windir\\*.log', \
                '$windir\\imsins.BAK', \
                '$windir\\OEWABLog.txt', \
                '$windir\\SchedLgU.txt', \
                '$windir\\ntbtlog.txt', \
                '$windir\\setuplog.txt', \
                '$windir\\Debug\\*.log', \
                '$windir\\Debug\\Setup\\UpdSh.log', \
                '$windir\\Debug\\UserMode\\*.log', \
                '$windir\\Debug\\UserMode\\ChkAcc.bak', \
                '$windir\\Debug\\UserMode\\userenv.bak', \
                '$windir\\pchealth\\helpctr\\Logs\\hcupdate.log', \
                '$windir\\security\\logs\\*.log', \
                '$windir\\security\\logs\\*.old', \
                '$windir\\system32\\TZLog.log', \
                '$windir\\system32\\config\\systemprofile\\Application Data\\Microsoft\\Internet Explorer\\brndlog.bak', \
                '$windir\\system32\\config\\systemprofile\\Application Data\\Microsoft\\Internet Explorer\\brndlog.txt', \
                '$windir\\system32\\LogFiles\\Firewall\\pfirewall.log*', \
                '$windir\\system32\\LogFiles\\Scm\\SCM.EVM*', \
                '$windir\\system32\\wbem\\Logs\\*.lo_', \
                '$windir\\system32\\wbem\\Logs\\*.log', )

            for path in paths:
                expanded = os.path.expandvars(path)
                for globbed in glob.iglob(expanded):
                    files += [ globbed ]

        # memory
        if 'linux2' == sys.platform and 'memory' == option_id:
            yield Command.Function(None, Memory.wipe_memory, _('Memory'))

        # most recently used documents list
        if 'posix' == os.name and 'recent_documents' == option_id:
            files += [ os.path.expanduser("~/.recently-used") ]

        # fixme http://www.freedesktop.org/wiki/Specifications/desktop-bookmark-spec

        if 'posix' == os.name and 'rotated_logs' == option_id:
            for path in Unix.rotated_logs():
                yield Command.Delete(path)


        # temporary files
        if 'posix' == os.name and 'tmp' == option_id:
            dirnames = [ '/tmp', '/var/tmp' ]
            for dirname in dirnames:
                for path in children_in_directory(dirname, True):
                    is_open = FileUtilities.openfiles.is_open(path)
                    ok = not is_open and os.path.isfile(path) and \
                        not os.path.islink(path) and \
                        FileUtilities.ego_owner(path) and \
                        not self.whitelisted(path)
                    if ok:
                        yield Command.Delete(path)

        # temporary files
        if 'nt' == os.name and 'tmp' == option_id:
            dirname = os.path.expandvars("$USERPROFILE\\Local Settings\\Temp\\")
            for filename in children_in_directory(dirname, True):
                yield Command.Delete(filename)
            dirname = os.path.expandvars("$windir\\temp\\")
            for filename in children_in_directory(dirname, True):
                yield Command.Delete(filename)


        # trash
        if 'posix' == os.name and 'trash' == option_id:
            dirname = os.path.expanduser("~/.Trash")
            for filename in children_in_directory(dirname, False):
                yield Command.Delete(filename)
            # fixme http://www.ramendik.ru/docs/trashspec.html
            # http://standards.freedesktop.org/basedir-spec/basedir-spec-0.6.html
            # ~/.local/share/Trash
            # * GNOME 2.22, Fedora 9
            # * KDE 4.1.3, Ubuntu 8.10
            dirname = os.path.expanduser("~/.local/share/Trash/files")
            for filename in children_in_directory(dirname, True):
                yield Command.Delete(filename)
            dirname = os.path.expanduser("~/.local/share/Trash/info")
            for filename in children_in_directory(dirname, True):
                yield Command.Delete(filename)
            dirname = os.path.expanduser("~/.local/share/Trash/expunged")
            # desrt@irc.gimpnet.org tells me that the trash
            # backend puts files in here temporary, but in some situations
            # the files are stuck.
            for filename in children_in_directory(dirname, True):
                yield Command.Delete(filename)

        # return queued files
        for filename in files:
            if os.path.lexists(filename):
                yield Command.Delete(filename)

        # clipboard
        if HAVE_GTK and 'clipboard' == option_id:
            def clear_clipboard():
                gtk.gdk.threads_enter()
                clipboard = gtk.clipboard_get()
                clipboard.set_text("")
                gtk.gdk.threads_leave()
                return 0
            yield Command.Function(None, clear_clipboard, _('Clipboard'))


        # recent documents
        if 'posix' == os.name and 'recent_documents' == option_id:
            # GNOME 2.26 (as seen on Ubuntu 9.04) will retain the list
            # in memory if it is simply deleted, so it must be shredded
            # (or at least truncated).
            pathname = os.path.expanduser("~/.recently-used.xbel")
            if os.path.lexists(pathname):
                if options.get('shred'):
                    yield Command.Shred(pathname)
                else:
                    yield Command.Truncate(pathname)


        # overwrite free space
        shred_drives = options.get_list('shred_drives')
        if 'free_disk_space' == option_id and shred_drives:
            for pathname in shred_drives:
                # TRANSLATORS: 'Free' could also be translated 'unallocated.'
                # %s expands to a path such as C:\ or /tmp/
                display = _("Overwrite free disk space %s") % pathname
                def wipe_path_func():
                    for ret in FileUtilities.wipe_path(pathname, idle = True):
                        # Yield control to GTK idle because this process
                        # is very slow.
                        yield ret
                    yield 0
                yield Command.Function(None, wipe_path_func, display)


        # MUICache
        if 'nt' == os.name and 'muicache' == option_id:
            keys = ( 'HKCU\\Software\\Microsoft\\Windows\\ShellNoRoam\\MUICache',
                'HKCU\\Software\\Classes\\Local Settings\\Software\\Microsoft\\Windows\\Shell\\MuiCache' )
            for key in keys:
                yield Command.Winreg(key, None)


        # prefetch
        if 'nt' == os.name and 'prefetch' == option_id:
            for path in glob.iglob(os.path.expandvars('$windir\\Prefetch\\*.pf')):
                yield Command.Delete(path)


        # recycle bin
        if 'nt' == os.name and 'recycle_bin' == option_id:
            for drive in Windows.get_fixed_drives():
                # TRANSLATORS: %s expands to a drive letter such as C:\ or D:\
                label = _("Recycle bin %s") % drive
                def emptyrecyclebin():
                    return Windows.empty_recycle_bin(drive, True)
                # fixme: enable size preview
                yield Command.Function(None, emptyrecyclebin, label)



    def whitelisted(self, pathname):
        """Return boolean whether file is whitelisted"""
        regexes = [
            '^/tmp/.truecrypt_aux_mnt.*/(control|volume)$',
            '^/tmp/.vbox-[^/]+-ipc/lock$',
            '^/tmp/.wine-[0-9]+/server-.*/lock$',
            '^/tmp/.X0-lock$',
            '^/tmp/gconfd-[^/]+/lock/ior$',
            '^/tmp/ksocket-[^/]+/(Arts_SoundServerV2|secret-cookie)$',
            '^/tmp/orbit-[^/]+/bonobo-activation-register[a-z0-9-]*.lock$',
            '^/tmp/orbit-[^/]+/bonobo-activation-server-[a-z0-9-]*ior$',
            '^/tmp/pulse-[^/]+/pid$' ]
        for regex in regexes:
            if None != re.match(regex, pathname):
                return True
        return False


# initialize "hard coded" (non-CleanerML) backends
backends = {}
backends["firefox"] = Firefox()
if 'posix' == os.name:
    backends["rpmbuild"] = rpmbuild()
backends["openofficeorg"] = OpenOfficeOrg()
backends["system"] = System()


def create_simple_cleaner(paths):
    cleaner = Cleaner()
    cleaner.add_option(option_id = 'files', name = '', description = '')
    cleaner.name = ''
    import Action
    import Command
    class CustomFileAction(Action.ActionProvider):
        action_key = '__customfileaction'
        def get_commands(self):
            for path in paths:
                yield Command.Shred(path)
    provider = CustomFileAction(None)
    cleaner.add_action('files', provider)
    return cleaner





