"""Layout and touch handling, independent of hardware and desktop commands."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Item:
    action: str
    label: str
    icon: str
    x: float
    width: float

    def contains(self, x):
        return self.x <= x < self.x + self.width


class Layout:
    def __init__(self):
        self.page = 'home'
        self.fn = False
        self.overlay = None
        self.state = {'volume': None, 'brightness': None, 'keyboard': None, 'workspace': 1, 'muted': False, 'locked': True}
        self.contact = None
        self.blocked = False
        self.pressed = None
        self.last_touch = 0

    def items(self):
        if self.overlay:
            return self.distribute([('cancel-auth', 'Cancel', 'back', 1),
                                    ('status', self.overlay, '', 12)])
        if self.fn:
            keys = [('esc', 'esc', '', 1)] + [(f'key:{i}', f'F{i}', '', 1) for i in range(1, 13)]
            return self.distribute(keys)
        if self.state['locked'] and self.page not in ('volume','brightness','keyboard'):
            return self.distribute([('esc','esc','',1), ('status','Screen locked','',6),
                                    ('volume',self.level('volume'),'volume',2),
                                    ('brightness',self.level('brightness'),'brightness',2),
                                    ('stock','Default','back',1.5)])
        if self.page == 'workspaces':
            return self.distribute([('back', 'Back', 'back', 1)] +
                                   [(f'workspace:{i}', str(i), '', 1) for i in range(1, 11)])
        if self.page in ('volume', 'brightness', 'keyboard'):
            value = self.state[self.page]
            label = '—' if value is None else f'{value}%'
            return self.distribute([('esc', 'esc', '', 1), ('back', 'Back', 'back', 1.2),
                                    ('spacer', '', '', 1.3),
                                    ('status', self.page.title(), self.page, 2.2),
                                    ('slider', label, '', 6),
                                    ('mute' if self.page == 'volume' else 'spacer',
                                     ('Unmute' if self.state['muted'] else 'Mute') if self.page == 'volume' else '',
                                     'volume' if self.page == 'volume' else '', 1.3),
                                    ('spacer', '', '', 2), ('launcher', '', 'omarchy', 1.1),
                                    ('stock', 'Default', 'back', 1.5)])
        return self.distribute([
            ('esc', 'esc', '', 0.85), ('launcher', '', 'omarchy', 1.05),
            ('workspaces', str(self.state['workspace']), 'workspaces', 1.2),
            ('screenshot', '', 'camera', 1), ('notifications', '', 'bell', 1),
            ('previous', '', 'previous', 0.85), ('play', '', 'play', 0.85), ('next', '', 'next', 0.85),
            ('volume', self.level('volume'), 'volume', 1.65),
            ('brightness', self.level('brightness'), 'brightness', 1.65),
            ('keyboard', '', 'keyboard', 1), ('stock', 'Default', 'back', 1.4)])

    def level(self, name):
        if name == 'volume' and self.state['muted']:
            return 'Muted'
        value = self.state[name]
        return '—' if value is None else f'{value}%'

    @staticmethod
    def distribute(specifications):
        gap, margin = 12, 8
        available = 2170 - 2 * margin - gap * (len(specifications) - 1)
        total = sum(item[3] for item in specifications)
        x, result = margin, []
        for action, label, icon, weight in specifications:
            width = available * weight / total
            result.append(Item(action, label, icon, x, width))
            x += width + gap
        return result

    def change_context(self, fn=None, overlay=None):
        if fn is not None and fn != self.fn or overlay != self.overlay:
            self.blocked = self.blocked or self.contact is not None
            self.contact, self.pressed = None, None
        if fn is not None:
            self.fn = fn
        self.overlay = overlay

    def handle(self, contacts):
        """Return typed actions; icon taps fire on release, sliders capture drags."""
        if len(contacts) > 1:
            self.blocked = True
            self.contact, self.pressed = None, None
            return []
        if not contacts:
            old, self.contact = self.contact, None
            self.pressed = None
            was_blocked, self.blocked = self.blocked, False
            if old is None or was_blocked or old['dragged'] or old['item'].action in ('slider', 'status', 'spacer'):
                return []
            return self.activate(old['item'].action)
        if self.blocked:
            return []
        identity, x, y = contacts[0]
        if self.contact is None:
            item = next((item for item in self.items() if item.contains(x)), None)
            if item is None:
                self.blocked = True
                return []
            self.contact = {'id': identity, 'x': x, 'y': y, 'item': item, 'dragged': False}
            self.pressed = item.action
        old = self.contact
        if identity != old['id']:
            self.blocked = True
            self.contact, self.pressed = None, None
            return []
        if old['item'].action == 'slider':
            if self.state[self.page] is None:
                return []
            return [('level', self.page, self.slider_value(old['item'], x, self.page))]
        if math.hypot(x - old['x'], y - old['y']) > 18:
            old['dragged'] = True
            self.pressed = None
        return []

    @staticmethod
    def slider_value(item, x, page):
        start, end = item.x + 34, item.x + item.width - 100
        value = round(max(0, min(1, (x - start) / (end - start))) * 100)
        return max(1 if page == 'brightness' else 0, value)

    def activate(self, action):
        if action in ('volume', 'brightness', 'keyboard', 'workspaces'):
            self.page = action
            return []
        if action == 'back':
            self.page = 'home'
            return []
        if action in ('status', 'spacer'):
            return []
        return [('action', action)]
