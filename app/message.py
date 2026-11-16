#------------------------ IMPORTS --------------------------#
from __future__ import annotations

from . import *
from .utils import sanitize
from re import sub


#------------------------- CLASSES ---------------------------#

@dataclass(slots=True, frozen=True)
class MessageCategory:
    '''Essential keyworks to categorize each message title.'''
    fish: str = 'You caught:'
    profile: str = 'Inventory of'
    charms: str = 'Charms are found in'
    buffs: str = 'current multipliers'
    quests: str = 'Quest List'
    leaderboard: str = '\'s leaderboard positions'


def extract_components_data(comps: list) -> tuple[list[str], dict[str, str]]:
    texts = []
    buttons = {}
    def recurse(items):
        if not items or not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            if 'content' in item and item['content']:
                texts.append(str(item['content']))
            if 'label' in item and 'custom_id' in item:
                buttons[item['label']] = str(item['custom_id'])
            if 'components' in item:
                recurse(item['components'])
    recurse(comps)
    return texts, buttons


@dataclass
class Message:
    '''Message class to convert raw events into usable messages.'''
    id: str = None
    play_id: str = None
    title: str = field(default=None, repr=False)
    description: str = field(default=None, repr=False)
    content: str = None
    items: list[str] = field(default_factory=list, repr=False)
    untitled: str = None
      
    @property
    def name(self) -> str:
        '''Returns the class name in the correct format.'''
        return f'{self.__class__.__name__}'
    
    def make(self, event: dict) -> None:
        '''Makes message schematics, assigning ids and attributes.'''
        self.reset()
        if not event or not isinstance(event, dict):
            return None

        self.content = event.get('content') or ''
        
        # 1. Extract components (buttons & text from new Discord Components V2)
        components = event.get('components', [])
        comp_texts = []
        buttons = {}
        if components and isinstance(components, list):
            comp_texts, buttons = extract_components_data(components)
            if 'Fish Again' in buttons:
                self.id = event.get('id')
                self.play_id = buttons['Fish Again']

        # 2. Extract embeds
        embeds = event.get('embeds', [])
        raw_title = ''
        raw_desc = ''
        if embeds and isinstance(embeds, list):
            for embed in embeds:
                if isinstance(embed, dict):
                    if embed.get('title'):
                        raw_title += str(embed.get('title')) + ' '
                    if embed.get('description'):
                        raw_desc += str(embed.get('description')) + '\n'
                    if embed.get('fields') and isinstance(embed.get('fields'), list):
                        for f in embed.get('fields'):
                            if isinstance(f, dict):
                                fname = str(f.get('name', ''))
                                fval = str(f.get('value', ''))
                                raw_desc += f"{fname}\n{fval}\n"
                    if embed.get('author') and isinstance(embed.get('author'), dict):
                        raw_title += str(embed.get('author').get('name', '')) + ' '

        # Merge component texts into raw_desc
        if comp_texts:
            comp_joined = '\n'.join(comp_texts)
            raw_desc = f"{raw_desc}\n{comp_joined}".strip() if raw_desc else comp_joined

        content = self.content or ''

        # 3. Categorize message
        # Check Fish
        if 'You caught' in raw_desc:
            self.title = 'You caught:'
            idx = raw_desc.find('You caught')
            self.description = raw_desc[idx + len('You caught'):].lstrip(':').strip()
        elif 'You caught' in content:
            self.title = 'You caught:'
            idx = content.find('You caught')
            self.description = content[idx + len('You caught'):].lstrip(':').strip()
        elif 'You caught' in raw_title:
            self.title = 'You caught:'
            self.description = raw_desc.strip() or content
        # Check Profile
        elif 'Inventory of' in raw_desc or 'Inventory of' in content or 'Inventory of' in raw_title:
            self.title = 'Inventory of'
            source = raw_desc if 'Inventory of' in raw_desc else (content if 'Inventory of' in content else raw_title)
            self.description = source[source.find('Inventory of'):].strip()
        # Check Charms
        elif 'Charms are found in' in raw_desc or 'Charms are found in' in content or 'Charms are found in' in raw_title:
            self.title = 'Charms are found in'
            source = raw_desc if 'Charms are found in' in raw_desc else (content if 'Charms are found in' in content else raw_title)
            self.description = source[source.find('Charms are found in'):].strip()
        # Check Buffs
        elif 'current multipliers' in raw_desc or 'current multipliers' in content or 'current multipliers' in raw_title:
            self.title = 'current multipliers'
            source = raw_desc if 'current multipliers' in raw_desc else (content if 'current multipliers' in content else raw_title)
            self.description = source[source.find('current multipliers'):].strip()
        # Check Quests
        elif 'Quest List' in raw_desc or 'Quest List' in content or 'Quest List' in raw_title:
            self.title = 'Quest List'
            source = raw_desc if 'Quest List' in raw_desc else (content if 'Quest List' in content else raw_title)
            self.description = source[source.find('Quest List'):].strip()
        # Check Leaderboard
        elif "'s leaderboard positions" in raw_desc or "'s leaderboard positions" in content or "'s leaderboard positions" in raw_title:
            self.title = "'s leaderboard positions"
            source = raw_desc if "'s leaderboard positions" in raw_desc else (content if "'s leaderboard positions" in content else raw_title)
            self.description = source[source.find("'s leaderboard positions"):].strip()
        else:
            self.untitled = sanitize(raw_desc.strip() or content)
        return None
    
    def build(self, extra_list: list = []) -> list:
        '''Builds message list ready to be displayed.'''
        #Todo: refactor this function
        self.items = []
        if not self.description:
            return self.items
        for line in self.description.split('\n'):
            final = ''
            if line.find('LEVEL UP!') > -1:
                #Level up information
                level = sub(r'[^\d+]', '', sub(r'<.+?> ', '', line))
                final = f'<< LEVEL UP: {int(level) - 1} -> {level} >>'
            elif line.find('<:') > -1:
                #Emotes 
                final = sub(r'  ', ' ', sub(r'<.+?>', '', line))
            elif line.find(':') > -1:
                #Duplicator Emote (and commom emotes)
                final = sub(r'  ', ' ', sub(r':.+?: ', '', line))
            elif line.find('#') > -1: 
                #Global boost information
                pass
            elif line == '' or line == None or line == '\n':
                pass
            else:
                final = line
            clean_line = final.encode('ascii', 'ignore').decode('ascii').strip()
            if clean_line:
                self.items.append(sub(r'[\*+]', '', clean_line))
        if extra_list != []:
            self.items = extra_list + self.items
        return self.items
    
    def reset(self) -> None:
        '''Reset values to default.'''
        self.title: str = None
        self.description: str = None
        self.content: str = None
        self.items: list[str] = []
        self.untitled: str = None
        return None
    
    def reset_ids(self) -> None:
        self.play_id = None
        self.id = None

