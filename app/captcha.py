#------------------------ IMPORTS --------------------------#
from __future__ import annotations

from . import *
from .utils import debugger
from .menu import NotificationPriority
import base64
from requests import get, post, exceptions
from threading import Thread
from time import sleep
from json import loads
from re import sub, search, findall

#------------------------ CONSTANTS --------------------------#
MAX_CAPTCHA_REGENS = 5

#------------------------- CLASSES ---------------------------#
class UnkownCaptchaError(Exception):
    pass

#Todo: make a captcha status (like scheduler class)


@dataclass
class Captcha:
    '''Catpcha class, detects and solves captchas.'''
    #Todo: split this class in chaptcha "controller" and captcha datatype
    #Pointers
    menu: BaseMenu = field(repr=False)
    
    #Components
    api_key: str = field(repr=False)
    answers: list = field(default_factory=list)
    captcha_image: str = None
    
    #Backend
    _ocr_url: str = field(default='https://api.ocr.space/parse/image', repr=False)
    _word_list: list[str] = field(init=False, repr=False)
    _raw_answers: list[str] = field(default_factory=list)
    _engines: list[int] = field(init=False, repr=False)
    _max_timeout: int = field(default=20, repr=False)
    _captcha_length: int = 6
    
    #Counters
    regens: int = 0
    
    #Flags
    busy: bool = False
    detected: bool = False
    solving: bool = False
    regenerating: bool = False

    #OCR Settings
    is_overlay_required: bool = field(default=False, repr=False)
    detect_orientation: bool = field(default=True, repr=False)
    scale: bool = field(default=False, repr=False)
    language: str = field(default='eng', repr=False)
    
    def __post_init__(self) -> None:
        self._word_list = ['captcha', 'verify', 'anti-bot']
        self._engines = [2, 1]
    
    @property
    def name(self) -> str:
        '''Returns the class name in the correct format.'''
        return f'{self.__class__.__name__}'
    
    def filter(self, value: str) -> str:
        '''Filters results from the API. Valid results -> alphanum between 4 and 8 chars'''
        if value:
            lines = [l.strip() for l in value.split('\n') if l.strip()]
            for line in reversed(lines):
                ans = sub('[^a-zA-Z0-9]', '', line)
                if 4 <= len(ans) <= 8 and ans.lower() not in ['verify', 'result', 'answer', 'code', 'regen']:
                    return ans
            ans = sub('[^a-zA-Z0-9]', '', value)
            if 4 <= len(ans) <= 8 and ans.lower() not in ['verify', 'result', 'answer', 'code', 'regen']:
                return ans
            return None
        return None
    
    def generate_candidates(self, ans: str) -> list[str]:
        '''Generates candidate variations for easily-confused OCR characters.'''
        candidates = [ans]
        swaps = [
            ('g', 'q'), ('q', 'g'),
            ('l', '1'), ('1', 'l'),
            ('0', 'O'), ('O', '0'),
            ('5', 'S'), ('S', '5'),
            ('2', 'Z'), ('Z', '2')
        ]
        for old, new in swaps:
            if old in ans:
                variant = ans.replace(old, new)
                if variant not in candidates:
                    candidates.append(variant)
        return candidates

    def request(self, engine: int) -> None:
        '''Makes a request to the OCR api and appends the result (if valid) to the answers list.'''
        if not self.detected or not self.captcha_image: 
            return None

        # Download image and convert to base64 to avoid Discord CDN blocking/expiring URL issues
        b64_image = None
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            img_r = get(self.captcha_image, headers=headers, timeout=6)
            if img_r.status_code == 200:
                b64_image = 'data:image/png;base64,' + base64.b64encode(img_r.content).decode()
        except Exception as e:
            debugger.log(e, f'{self.name} - download image')

        payload = {
            'apikey': self.api_key,
            'isOverlayRequired': self.is_overlay_required,
            'detectOrientation': self.detect_orientation,
            'scale': True,
            'OCREngine': engine,
            'language': self.language
        }
        if b64_image:
            payload['base64Image'] = b64_image
        else:
            payload['url'] = self.captcha_image
        
        try:
            req = post(self._ocr_url, data=payload, timeout=self._max_timeout)
            response = loads(req.content.decode())
        except exceptions.ReadTimeout as e:
            self.menu.notify(f'[!] Engine {engine} took too long to respond.', NotificationPriority.LOW)
            if engine == self._engines[-1]:
                self.solving = False
            debugger.log(e, f'{self.name} - request timeout | {self}')
            return None
        except Exception as e:
            debugger.log(e, f'{self.name} - request')
            if engine == self._engines[-1]:
                self.solving = False
            return None
        
        if response.get('OCRExitCode') == 1:
            if self.detected and response.get('ParsedResults'):
                parsed_text = response['ParsedResults'][0].get('ParsedText', '')
                answer = self.filter(parsed_text)
                if answer:
                    candidates = self.generate_candidates(answer)
                    for cand in reversed(candidates):
                        if cand not in self.answers and self.detected:
                            self.answers.append(cand)
                    self.menu.notify(f'[*] OCR decoded: "{answer}" (candidates: {candidates})')
            
            if engine == self._engines[-1]:
                self.solving = False
            return None
        else:
            if not self.detected: 
                return None
            self.menu.notify(
                f'[!] Engine {engine} OCR API error -> ExitCode: {response.get("OCRExitCode")}.', 
                NotificationPriority.HIGH
            )
            if engine == self._engines[-1]:
                self.solving = False
            return None     
            
    def detect(self, event: dict) -> bool:
        '''Attempts to detect any captchas in the event.'''
        self.busy = True

        for target in self._word_list:
            if str(event).lower().find(target) > -1:
                self.detected = True
                break
        
        if self.detected:
            # 1. Collect all text from content, embeds, and components
            content = event.get('content', '') or ''
            embed_texts = []
            embeds = event.get('embeds', [])
            if isinstance(embeds, list):
                for embed in embeds:
                    if isinstance(embed, dict):
                        if embed.get('title'):
                            embed_texts.append(str(embed.get('title')))
                        if embed.get('description'):
                            embed_texts.append(str(embed.get('description')))
                        for f in embed.get('fields', []):
                            if isinstance(f, dict):
                                embed_texts.append(str(f.get('name', '')))
                                embed_texts.append(str(f.get('value', '')))

            # Extract text from nested components (Discord Components V2)
            comp_texts = []
            def recurse_comp_texts(items):
                if not items or not isinstance(items, list): return
                for it in items:
                    if isinstance(it, dict):
                        if it.get('content'): comp_texts.append(str(it['content']))
                        if it.get('components'): recurse_comp_texts(it['components'])
            recurse_comp_texts(event.get('components', []))

            all_text = f"{content}\n" + "\n".join(embed_texts + comp_texts)

            # 2. Check for plain text captcha code (cleaning markdown characters like *, `, _, ~)
            clean_text = sub(r'[*_`~#]', '', all_text)
            code_match = search(r'Code:\s*([a-zA-Z0-9]{3,8})', clean_text)
            if not code_match:
                code_match = search(r'Please use /verify\s+([a-zA-Z0-9]{3,8})', clean_text)
            if code_match:
                code = code_match.group(1).strip()
                if code.lower() not in ['result', 'answer', 'code', 'regen', 'with', 'this']:
                    self.answers = [code]
                    self.captcha_image = None
                    self.busy = False
                    debugger.log(f'Text captcha detected with code: {code}', f'{self.name} - detect')
                    return True

            # 3. Check for image inside Components V2 (type: 12 Media Gallery)
            def recurse_comp_media(items):
                if not items or not isinstance(items, list): return None
                for it in items:
                    if isinstance(it, dict):
                        if 'media' in it and isinstance(it['media'], dict) and it['media'].get('url'):
                            return it['media']['url']
                        if 'items' in it and isinstance(it['items'], list):
                            res = recurse_comp_media(it['items'])
                            if res: return res
                        if 'components' in it and isinstance(it['components'], list):
                            res = recurse_comp_media(it['components'])
                            if res: return res
                return None

            comp_img = recurse_comp_media(event.get('components', []))
            if comp_img:
                self.captcha_image = comp_img
                self.busy = False
                debugger.log(f'Captcha image found in Components V2: {self.captcha_image}', f'{self.name} - detect')
                return True

            # 4. Check for image in attachments
            for attachment in event.get('attachments', []):
                if isinstance(attachment, dict):
                    if attachment.get('url'):
                        self.captcha_image = attachment['url']
                        self.busy = False
                        return True
                    if attachment.get('proxy_url'):
                        self.captcha_image = attachment['proxy_url']
                        self.busy = False
                        return True

            # 5. Check for image in embeds
            for embed in embeds:
                if isinstance(embed, dict):
                    for img_key in ['image', 'thumbnail']:
                        if img_key in embed and isinstance(embed[img_key], dict):
                            img_obj = embed[img_key]
                            if img_obj.get('url'):
                                self.captcha_image = img_obj['url']
                                self.busy = False
                                return True
                            if img_obj.get('proxy_url'):
                                self.captcha_image = img_obj['proxy_url']
                                self.busy = False
                                return True

            # 6. Regex search across the entire raw event string for any Discord CDN image
            event_str = str(event)
            found_urls = findall(r'https?://(?:cdn|media)\.discordapp\.(?:com|net)/attachments/[^\s"\'<>]+\.(?:png|jpg|jpeg|webp|gif)[^\s"\'<>]*', event_str)
            if not found_urls:
                found_urls = findall(r'https?://[^\s"\'<>]+\.(?:png|jpg|jpeg|webp|gif)[^\s"\'<>]*', event_str)
            if found_urls:
                filtered = [u for u in found_urls if 'emojis' not in u and 'avatars' not in u]
                if filtered:
                    self.captcha_image = filtered[0]
                    self.busy = False
                    debugger.log(f'Captcha image URL found via regex: {self.captcha_image}', f'{self.name} - detect')
                    return True

            # Captcha detected but no image or explicit text code found
            debugger.log(f'Captcha detected but no image or explicit text code: {all_text}', f'{self.name} - detect')
            self.busy = False
            return True
        else:
            self.busy = False
            self.reset()
            return False

    def solve(self) -> None:
        '''Start engine threads to solve the captcha.'''
        self.busy = True
        self.regenerating = False
        
        # If code was already extracted from text, skip OCR
        if len(self.answers) > 0:
            self.solving = False
            self.busy = False
            return None
        
        if not self.captcha_image:
            self.solving = False
            self.busy = False
            return None

        self.solving = True
        self.answers = [] #Reset answers for redundancy
        
        for engine in self._engines:
            async_request = Thread(target=self.request, args=(engine,), daemon=True)
            async_request.start()
            sleep(0.5)
        
        self.busy = False
        return None
    
    def reset(self) -> None:
        '''Reset all attrs to default values.'''
        self.answers = []
        self.busy = False
        self.detected = False
        self.solving = False
        self.regenerating = False
        self.captcha_image = None
        self.regens = 0
        return None
        
        
# --------- INIT ---------#
if __name__ == "__main__":
    pass