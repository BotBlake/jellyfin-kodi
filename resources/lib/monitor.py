# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import threading
import sys

import xbmc
import xbmcgui

import connect
import downloader
import player
from client import get_device_id
from objects import Actions, PlaylistWorker, on_play, on_update, special_listener
from helper import _, settings, window, dialog, event, api, JSONRPC
from emby import Emby

#################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

#################################################################################################


class Monitor(xbmc.Monitor):

    servers = []

    def __init__(self):

        self.player = player.Player()
        self.device_id = get_device_id()
        self.listener = Listener(self)
        self.listener.start()
        xbmc.Monitor.__init__(self)

    def onScanStarted(self, library):
        LOG.info("-->[ kodi scan/%s ]", library)

    def onScanFinished(self, library):
        LOG.info("--<[ kodi scan/%s ]", library)

    def onNotification(self, sender, method, data):
        
        if sender.lower() not in ('plugin.video.emby', 'xbmc'):
            return

        if sender == 'plugin.video.emby':
            method = method.split('.')[1]

            if method not in ('GetItem', 'ReportProgressRequested', 'LoadServer',
                              'GetServerAddress', 'GetPlaybackInfo', 'Browse', 'GetImages', 'GetToken',
                              'PlayPlaylist', 'Play', 'GetIntros', 'GetAdditionalParts', 'RefreshItem',
                              'FavoriteItem', 'DeleteItem', 'AddUser', 'GetSession', 'GetUsers', 'GetThemes',
                              'GetTheme', 'Playstate', 'GeneralCommand'):
                return

            data = json.loads(data)[0]
        else:
            if method not in ('Player.OnPlay', 'VideoLibrary.OnUpdate', 'System.OnSleep'):
                return

            data = json.loads(data)

        if method != 'LoadServer' and data.get('ServerId') and data['ServerId'] not in self.servers:

            try:
                connect.Connect().register(data['ServerId'])
                self.server_instance(data['ServerId'])
            except Exception as error:

                LOG.error(error)
                dialog("ok", heading="{emby}", line1=_(33142))

                return

        server = Emby(data.get('ServerId'))

        if method == 'GetItem':

            item = server['api'].get_item(data['Id'])
            window('emby_%s.json' % data['VoidName'], item)
            LOG.debug("--->[ beacon/emby_%s.json ] sent", data['VoidName'])

        elif method == 'GetAdditionalParts':

            item = server['api'].get_additional_parts(data['Id'])
            window('emby_%s.json' % data['VoidName'], item)
            LOG.debug("--->[ beacon/emby_%s.json ] sent", data['VoidName'])

        elif method == 'GetIntros':

            item = server['api'].get_intros(data['Id'])
            window('emby_%s.json' % data['VoidName'], item)
            LOG.debug("--->[ beacon/emby_%s.json ] sent", data['VoidName'])

        elif method == 'GetImages':

            item = server['api'].get_images(data['Id'])
            window('emby_%s.json' % data['VoidName'], item)
            LOG.debug("--->[ beacon/emby_%s.json ] sent", data['VoidName'])

        elif method == 'GetServerAddress':

            server_address = server['auth/server-address']
            window('emby_%s.json' % data['VoidName'], server_address)
            LOG.debug("--->[ beacon/emby_%s.json ] sent", data['VoidName'])

        elif method == 'GetPlaybackInfo':

            sources = server['api'].get_play_info(data['Id'], data['Profile'])
            window('emby_%s.json' % data['VoidName'], sources)
            LOG.debug("--->[ beacon/emby_%s.json ] sent", data['VoidName'])

        elif method == 'GetLiveStream':

            sources = server['api'].get_play_info(data['Id'], data['PlaySessionId'], data['Token'], data['Profile'])
            window('emby_%s.json' % data['VoidName'], sources)
            LOG.debug("--->[ beacon/emby_%s.json ] sent", data['VoidName'])

        elif method == 'GetToken':

            token = server['auth/token']
            window('emby_%s.json' % data['VoidName'], token)
            LOG.debug("--->[ beacon/emby_%s.json ] sent", data['VoidName'])

        elif method == 'GetSession':

            session = server['api'].get_device(self.device_id)
            window('emby_%s.json' % data['VoidName'], session)
            LOG.debug("--->[ beacon/emby_%s.json ] sent", data['VoidName'])

        elif method == 'GetUsers':

            users = server['api'].get_users(data.get('IsDisabled', True), data.get('IsHidden', True))
            window('emby_%s.json' % data['VoidName'], users)
            LOG.debug("--->[ beacon/emby_%s.json ] sent", data['VoidName'])

        elif method == 'GetThemes':

            if data['Type'] == 'Video':
                theme = server['api'].get_items_theme_video(data['Id'])
            else:
                theme = server['api'].get_items_theme_song(data['Id'])

            window('emby_%s.json' % data['VoidName'], theme)
            LOG.debug("--->[ beacon/emby_%s.json ] sent", data['VoidName'])

        elif method == 'GetTheme':

            theme = server['api'].get_themes(data['Id'])
            window('emby_%s.json' % data['VoidName'], theme)
            LOG.debug("--->[ beacon/emby_%s.json ] sent", data['VoidName'])

        elif method == 'Browse':

            result = downloader.get_filtered_section(data.get('Id'), data.get('Media'), data.get('Limit'),
                                                     data.get('Recursive'), data.get('Sort'), data.get('SortOrder'), 
                                                     data.get('Filters'), data.get('ServerId'))
            window('emby_%s.json' % data['VoidName'], result)
            LOG.debug("--->[ beacon/emby_%s.json ] sent", data['VoidName'])


        elif method == 'RefreshItem':
            server['api'].refresh_item(data['Id'])

        elif method == 'FavoriteItem':
            server['api'].favorite(data['Id'], data['Favorite'])

        elif method == 'DeleteItem':
            server['api'].delete_item(data['Id'])

        elif method == 'PlayPlaylist':

            server['api'].post_session(server['config/app.session'], "Playing", {
                'PlayCommand': "PlayNow",
                'ItemIds': data['Id'],
                'StartPositionTicks': 0
            })

        elif method == 'Play':

            items = server['api'].get_items(data['ItemIds'])
            PlaylistWorker(data.get('ServerId'), items['Items'], data['PlayCommand'] == 'PlayNow',
                           data.get('StartPositionTicks', 0), data.get('AudioStreamIndex'),
                           data.get('SubtitleStreamIndex')).start()

        elif method == 'ReportProgressRequested':
            self.player.report_playback(data['Report'])

        elif method == 'Playstate':
            self.playstate(data)

        elif method == 'GeneralCommand':
            self.general_commands(data)

        elif method == 'LoadServer':
            self.server_instance(data['ServerId'])

        elif method == 'AddUser':
            server['api'].session_add_user(server['config/app.session'], data['Id'], data['Add'])
            self.additional_users(server)

        elif method == 'System.OnSleep':
            self.servers = []

        elif method == 'Player.OnPlay':
            on_play(data, server)

        elif method == 'VideoLibrary.OnUpdate':
            on_update(data, server)

    def server_instance(self, server_id=None):

        server = Emby(server_id)
        self.post_capabilities(server)

        if server_id is not None:
            self.servers.append(server_id)
        elif settings('additionalUsers'):

            users = settings('additionalUsers').split(',')
            all_users = server['api'].get_users()

            for additional in users:
                for user in all_users:

                    if user['Name'].lower() in additional.decode('utf-8').lower():
                        server['api'].session_add_user(server['config/app.session'], user['Id'], True)

            self.additional_users(server)

    def post_capabilities(self, server):

        server['api'].post_capabilities({
            'PlayableMediaTypes': "Audio,Video",
            'SupportsMediaControl': True,
            'SupportedCommands': (
                "MoveUp,MoveDown,MoveLeft,MoveRight,Select,"
                "Back,ToggleContextMenu,ToggleFullscreen,ToggleOsdMenu,"
                "GoHome,PageUp,NextLetter,GoToSearch,"
                "GoToSettings,PageDown,PreviousLetter,TakeScreenshot,"
                "VolumeUp,VolumeDown,ToggleMute,SendString,DisplayMessage,"
                "SetAudioStreamIndex,SetSubtitleStreamIndex,"
                "SetRepeatMode,"
                "Mute,Unmute,SetVolume,"
                "Play,Playstate,PlayNext,PlayMediaSource"
            ),
            'IconUrl': "https://raw.githubusercontent.com/MediaBrowser/plugin.video.emby/develop/kodi_icon.png",
        })

        session = server['api'].get_device(self.device_id)
        server['config']['app.session'] = session[0]['Id']

    def additional_users(self, server):

        ''' Setup additional users images.
        '''
        for i in range(10):
            window('EmbyAdditionalUserImage.%s' % i, clear=True)

        try:
            session = server['api'].get_device(self.device_id)
        except Exception as error:
            LOG.error(error)

            return

        for index, user in enumerate(session[0]['AdditionalUsers']):

            info = server['api'].get_user(user['UserId'])
            image = api.API(info, server['config/auth.server']).get_user_artwork(user['UserId'])
            window('EmbyAdditionalUserImage.%s' % index, image)
            window('EmbyAdditionalUserPosition.%s' % user['UserId'], str(index))

    def playstate(self, data):

        ''' Emby playstate updates.
        '''
        command = data['Command']
        actions = {
            'Stop': self.player.stop,
            'Unpause': self.player.pause,
            'Pause': self.player.pause,
            'PlayPause': self.player.pause,
            'NextTrack': self.player.playnext,
            'PreviousTrack': self.player.playprevious
        }
        if command == 'Seek':

            if self.player.isPlaying():

                seektime = data['SeekPositionTicks'] / 10000000.0
                self.player.seekTime(seektime)
                LOG.info("[ seek/%s ]", seektime)

        elif command in actions:

            actions[command]()
            LOG.info("[ command/%s ]", command)

    def general_commands(self, data):

        ''' General commands from Emby to control the Kodi interface.
        '''
        command = data['Name']
        args = data['Arguments']

        if command in ('Mute', 'Unmute', 'SetVolume',
                       'SetSubtitleStreamIndex', 'SetAudioStreamIndex', 'SetRepeatMode'):

            if command == 'Mute':
                xbmc.executebuiltin('Mute')
            elif command == 'Unmute':
                xbmc.executebuiltin('Mute')
            elif command == 'SetVolume':
                xbmc.executebuiltin('SetVolume(%s[,showvolumebar])' % args['Volume'])
            elif command == 'SetRepeatMode':
                xbmc.executebuiltin('xbmc.PlayerControl(%s)' % args['RepeatMode'])
            elif command == 'SetAudioStreamIndex':
                self.player.set_audio_subs(args['Index'])
            elif command == 'SetSubtitleStreamIndex':
                self.player.set_audio_subs(None, args['Index'])

            self.player.report_playback()

        elif command == 'DisplayMessage':
            dialog("notification", heading=args['Header'], message=args['Text'],
                   icon="{emby}", time=int(settings('displayMessage'))*1000)

        elif command == 'SendString':
            JSONRPC('Input.SendText').execute({'text': args['String'], 'done': False})

        elif command == 'GoHome':
            JSONRPC('GUI.ActivateWindow').execute({'window': "home"})

        elif command == 'Guide':
            JSONRPC('GUI.ActivateWindow').execute({'window': "tvguide"})

        elif command in ('MoveUp', 'MoveDown', 'MoveRight', 'MoveLeft'):
            actions = {
                'MoveUp': "Input.Up",
                'MoveDown': "Input.Down",
                'MoveRight': "Input.Right",
                'MoveLeft': "Input.Left"
            }
            JSONRPC(actions[command]).execute()

        else:
            builtin = {

                'ToggleFullscreen': 'Action(FullScreen)',
                'ToggleOsdMenu': 'Action(OSD)',
                'ToggleContextMenu': 'Action(ContextMenu)',
                'Select': 'Action(Select)',
                'Back': 'Action(back)',
                'PageUp': 'Action(PageUp)',
                'NextLetter': 'Action(NextLetter)',
                'GoToSearch': 'VideoLibrary.Search',
                'GoToSettings': 'ActivateWindow(Settings)',
                'PageDown': 'Action(PageDown)',
                'PreviousLetter': 'Action(PrevLetter)',
                'TakeScreenshot': 'TakeScreenshot',
                'ToggleMute': 'Mute',
                'VolumeUp': 'Action(VolumeUp)',
                'VolumeDown': 'Action(VolumeDown)',
            }
            if command in builtin:
                xbmc.executebuiltin(builtin[command])


class Listener(threading.Thread):

    stop_thread = False

    def __init__(self, monitor):
        self.monitor = monitor

        threading.Thread.__init__(self)

    def run(self):

        ''' Detect the resume dialog for widgets.
            Detect external players.
        '''
        LOG.warn("--->[ listener ]")

        while not self.stop_thread:
            special_listener()

            if self.monitor.waitForAbort(0.5):
                # Abort was requested while waiting. We should exit
                break

        LOG.warn("---<[ listener ]")

    def stop(self):
        self.stop_thread = True
