"""Small launch policy; independent of Windows, Tk and native memory access."""
class LaunchError(RuntimeError):
    pass


class LaunchPolicy:
    def __init__(self, timeout=300, stable_seconds=1.5):
        self.timeout = timeout
        self.stable_seconds = stable_seconds
        self.started = None
        self.identity = None
        self.menu_token = None
        self.menu_since = None
        self.activation_attempted = False
        self.finished = False
        self.not_before_creation_time = None

    def start(self, existing, now, not_before_creation_time=None):
        if self.started is not None:
            raise LaunchError('This launcher has already started Anno.')
        if existing:
            raise LaunchError('Anno is already running. Close Anno, then use this shortcut again.')
        self.started = now
        self.not_before_creation_time = not_before_creation_time

    def observe(self, process_ids, observation, now):
        if self.finished or self.activation_attempted:
            return 'inactive'
        if self.started is None:
            raise LaunchError('The launch has not started.')
        if now - self.started > self.timeout:
            raise LaunchError('Anno did not reach its main menu in time. Finish any Ubisoft startup screen, close Anno, then try again.')
        if len(process_ids) > 1:
            if self.identity is not None:
                raise LaunchError('More than one Anno process is running. Close them and try again.')
            # Ubisoft may briefly overlap its bootstrap and final game. Nothing
            # is activated until exactly one fresh, verified menu remains.
            self.menu_token = self.menu_since = None
            return 'waiting_for_game'
        if not process_ids:
            if self.identity is not None:
                raise LaunchError('Anno closed before World Settings could be enabled.')
            self.menu_token = self.menu_since = None
            return 'waiting_for_game'
        if self.identity is not None and process_ids[0] != self.identity[0]:
            raise LaunchError('The Anno process changed during launch. Close it and try again.')
        if observation is None:
            self.menu_token = self.menu_since = None
            return 'waiting_for_menu'
        if observation.get('state') == 'unsafe':
            raise LaunchError(observation.get('reason') or 'This Anno process cannot be activated safely.')
        creation = observation.get('process_creation_time')
        pid = observation.get('pid')
        if pid != process_ids[0]:
            raise LaunchError('Anno changed while its startup was being checked. Close it and try again.')
        if type(creation) is int and creation > 0:
            if (self.not_before_creation_time is not None
                    and creation < self.not_before_creation_time):
                raise LaunchError('This Anno process predates the shortcut launch. Close Anno and try again.')
            if self.identity is not None and (pid, creation) != self.identity:
                raise LaunchError('The Anno process restarted during launch. Close it and try again.')
        if observation.get('state') != 'menu':
            self.menu_token = self.menu_since = None
            return 'waiting_for_menu'
        if (type(creation) is not int or creation <= 0
                or observation.get('menu_proof_verified') is not True):
            raise LaunchError('Anno reached an unsupported startup screen. No activation was attempted.')
        # Pin only after a positively identified main menu; a disposable Ubisoft
        # bootstrap process can be replaced before this point without mutation.
        if self.identity is None:
            self.identity = (pid, creation)
        token = (self.identity, observation.get('hwnd'), observation.get('frame_pointer'))
        if not all(token[1:]):
            raise LaunchError('The main-menu check is incomplete. No activation was attempted.')
        if token != self.menu_token:
            self.menu_token, self.menu_since = token, now
            return 'waiting_for_menu'
        if now - self.menu_since < self.stable_seconds:
            return 'waiting_for_menu'
        # Set before handing control to any code that can load the DLL. A
        # timeout, partial activation, exception or second click cannot retry.
        self.activation_attempted = True
        return 'activate'

    def complete(self):
        if not self.activation_attempted or self.finished:
            raise LaunchError('Unexpected activation completion.')
        self.finished = True
