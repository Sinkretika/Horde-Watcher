"""Horde Watcher v1.5. Read-only public-source monitor; never controls WoW."""
import json, os, re, threading, webbrowser, winsound, time, ctypes, sys, traceback
from datetime import datetime
from pathlib import Path
import tkinter as tk
import customtkinter as ctk
from PIL import Image
import requests

# Guard against delayed focus callbacks targeting already-destroyed CTk widgets.
_original_focus_set = tk.Misc.focus_set
def _safe_focus_set(self):
    try:
        if self.winfo_exists():
            return _original_focus_set(self)
    except tk.TclError as exc:
        if "bad window path name" not in str(exc):
            raise
tk.Misc.focus_set = _safe_focus_set

ROOT=Path(os.environ.get('APPDATA',str(Path.home())))/'HordeWatcher'; ROOT.mkdir(parents=True,exist_ok=True)
SEEN=ROOT/'seen.json'; SETTINGS=ROOT/'settings.json'
ASSETS=Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
def write_error(kind, exc_type, exc, tb):
 try:
  with (ROOT/'errors.log').open('a', encoding='utf-8') as f:
   f.write('\n['+datetime.now().isoformat(timespec='seconds')+'] '+kind+'\n')
   traceback.print_exception(exc_type, exc, tb, file=f)
 except OSError: pass

def global_exception(exc_type, exc, tb):
 write_error('Unhandled exception', exc_type, exc, tb)
sys.excepthook=global_exception

SOURCES=[('Reddit · r/wow','https://www.reddit.com/r/wow/search.json?q=EU%20PvP%20Horde%20create&restrict_sr=1&sort=new&t=week&limit=30'),('Reddit · global','https://www.reddit.com/search.json?q=%22EU%20PvP%22%20%22Horde%22%20%22create%22&sort=new&t=week&limit=30'),('Blizzard EU','https://eu.forums.blizzard.com/en/wow/search.json?q=EU%20PvP%20Horde%20order%3Alatest')]
HEADERS={'User-Agent':'HordeWatcher/1.4 (public read-only monitoring)','Accept':'application/json'}
EU=re.compile(r'\bEU\b|europe(?:an)?',re.I); PVP=re.compile(r'\bPVP\b',re.I); HORDE=re.compile(r'\bhorde\b',re.I)
POS=re.compile(r'\b(open(?:ed)?|unlocked|available|enabled|lifted|removed|succeeded|successfully|created|creation|register(?:ed)?|registration)\b',re.I)
NEG=re.compile(r'\b(still locked|still closed|cannot|can.t|unable|not open|not available|failed|no luck|when will|waiting|is it open|anyone able|anyone managed)\b',re.I)
EXCLUDE=re.compile(r'\b(NA\s*PVP|US\s*PVP|RP\s*[- ]?PVP|PVE)\b',re.I)
ACCENT='#823D46'; GREEN='#4BB78A'; AMBER='#D4A255'; RED='#D75D65'
P={
'dark':{'bg':'#191B21','card':'#292C35','card2':'#323641','text':'#F5F5F7','muted':'#AEB2BF','border':'#373B45','button':'#343741','hover':'#414550'},
'light':{'bg':'#F2F3F6','card':'#FFFFFF','card2':'#F0F1F5','text':'#292B34','muted':'#6C7180','border':'#E5E6EB','button':'#E8E9EF','hover':'#DCDDE6'}}
WORDS={
'ru':{'subtitle':'EU PvP · Орда','active':'Мониторинг активен','checking':'Проверка источников…','issues':'Проблемы с источниками','offline':'Мониторинг остановлен','desc':'Проверка источников по расписанию','check':'⟳  Проверить сейчас','log':'Журнал событий','settings':'Настройки','test':'Тест уведомления','latest':'Последние события','all':'Открыть журнал  →','empty':'Пока нет новых подходящих сообщений','notice':'Индикатор показывает работу мониторинга, не открытие регистрации.','last':'Последняя проверка','never':'ещё не было','every':'Каждые {n} мин','lang':'Язык','theme':'Тема','interval':'Интервал (мин)','close':'Закрыть','sources':'Источники','saved':'Настройки сохраняются автоматически','testhead':'Проверка уведомления','testbody':'Тест звука и окна. Открытие регистрации не обнаружено.','unverified':'Возможное открытие · не подтверждено','needsreview':'Сообщение Blizzard EU · требует проверки','general':'Информация','first':'Первый запуск: старые публикации сохранены без уведомлений','none':'Новых подходящих публикаций нет','error':'Ошибка источника','report':'Сообщения игроков и форумные темы не являются официальным подтверждением.','open':'Открыть источник','ok':'Понятно','available':'Доступен','unavailable':'Недоступен','waiting':'Ожидание','journal':'Журнал событий','noentries':'Записей пока нет','platforms':'Состояние платформ'},
'en':{'subtitle':'EU PvP · Horde','active':'Monitoring active','checking':'Checking sources…','issues':'Source connection issues','offline':'Monitoring stopped','desc':'Checking sources on schedule','check':'⟳  Check now','log':'Event log','settings':'Settings','test':'Test notification','latest':'Recent activity','all':'Open event log  →','empty':'No new matching messages yet','notice':'The indicator shows monitoring health, not registration availability.','last':'Last checked','never':'not checked yet','every':'Every {n} min','lang':'Language','theme':'Theme','interval':'Interval (min)','close':'Close','sources':'Sources','saved':'Settings are saved automatically','testhead':'Notification test','testbody':'Sound and popup test. No registration opening was detected.','unverified':'Possible opening · unverified','needsreview':'Blizzard EU post · needs review','general':'Information','first':'First run: existing posts saved without alerts','none':'No new matching posts','error':'Source error','report':'Player reports and forum threads are not official confirmation.','open':'Open source','ok':'OK','available':'Available','unavailable':'Unavailable','waiting':'Waiting','journal':'Event log','noentries':'No entries yet','platforms':'Platform status'}}

def read_json(path,default):
 try:return json.loads(path.read_text(encoding='utf-8'))
 except (OSError,ValueError):return default

def candidate(title,body):
 s=(title+' '+body)[:10000]
 return all(p.search(s) for p in (EU,PVP,HORDE,POS)) and not NEG.search(s) and not EXCLUDE.search(s)

def collect():
 posts=[];errors=[];stats=[]
 for name,url in SOURCES:
  count=0
  try:
   r=requests.get(url,headers=HEADERS,timeout=15);r.raise_for_status();data=r.json()
   if name.startswith('Reddit'):
    for item in data.get('data',{}).get('children',[]):
     d=item.get('data',{});uid=d.get('id')
     if uid:posts.append((name,'reddit:'+str(uid),d.get('title',''),d.get('selftext',''),'https://www.reddit.com'+d.get('permalink',''),d.get('created_utc',0)));count+=1
   else:
    for p in data.get('topics',[]):
     uid=p.get('id')
     if uid:posts.append((name,'blizzard:'+str(uid),p.get('title',''),'','https://eu.forums.blizzard.com/en/wow/t/'+str(p.get('slug',''))+'/'+str(uid),0));count+=1
    for p in data.get('posts',[]):
     uid=p.get('id')
     if uid:posts.append((name,'blizzardpost:'+str(uid),p.get('topic_title',''),re.sub('<[^>]+>',' ',p.get('blurb','')),'https://eu.forums.blizzard.com/en/wow/t/'+str(p.get('topic_id',''))+'/'+str(p.get('post_number',1)),0));count+=1
  except requests.HTTPError as e:errors.append((name,'HTTP '+str(e.response.status_code)))
  except (requests.RequestException,ValueError,TypeError,KeyError) as e:errors.append((name,type(e).__name__+': '+str(e)[:120]))
  stats.append((name,count))
 return posts,errors,stats

class App:
 def __init__(self):
  cfg=read_json(SETTINGS,{})
  self.lang=cfg.get('language','ru') if cfg.get('language') in WORDS else 'ru'
  self.theme=cfg.get('theme','dark') if cfg.get('theme') in ('dark','light') else 'dark'
  self.interval=int(cfg.get('interval',5)) if str(cfg.get('interval',5)) in ('2','5','10','15','30') else 5
  self.seen=set(read_json(SEEN,[]));self.first=not SEEN.exists();self.running=True;self.busy=False;self.last=None;self.errors=[];self.stats=[];self.events=[];self.logs=[];self.next_check=time.monotonic()+self.interval*60
  self.root=ctk.CTk();self.root.title('Horde Watcher | EU PvP');self.root.geometry('670x640');self.root.minsize(610,560)
  self.root.report_callback_exception=lambda et,e,tb:write_error('Tk callback',et,e,tb)
  try:self.root.iconbitmap(str(ASSETS/'horde.ico'))
  except (OSError,tk.TclError):pass
  self.root.overrideredirect(True)
  self.root.bind('<Map>',self.on_map)
  self._taskbar_registered=False
  self.root.after(250,self.register_taskbar)
  self.root.protocol('WM_DELETE_WINDOW',self.quit)
  self.logo=ctk.CTkImage(light_image=Image.open(ASSETS/'horde_logo.png'),dark_image=Image.open(ASSETS/'horde_logo.png'),size=(43,70))
  self.modal=None;self.apply_theme();self.root.after(650,self.check);self.root.after(1000,self.tick)
 def t(self,k):return WORDS[self.lang][k]
 def effective_theme(self):return self.theme
 def colors(self):return P[self.effective_theme()]
 def save(self):
  SETTINGS.write_text(json.dumps({'language':self.lang,'theme':self.theme,'interval':self.interval},ensure_ascii=False,indent=2),encoding='utf-8')
 def clear(self,widget):
  for child in widget.winfo_children():child.destroy()
 def label(self,parent,text,size=13,bold=False,color=None,**kwargs):
  return ctk.CTkLabel(parent,text=text,font=ctk.CTkFont(family='Segoe UI',size=size,weight='bold' if bold else 'normal'),text_color=color or self.colors()['text'],**kwargs)
 def button(self,parent,text,command,primary=False,width=130,height=39):
  p=self.colors();return ctk.CTkButton(parent,text=text,command=command,width=width,height=height,corner_radius=11,fg_color=ACCENT if primary else p['button'],hover_color='#9B4B57' if primary else p['hover'],text_color='#FFFFFF' if primary else p['text'],font=ctk.CTkFont(family='Segoe UI',size=13,weight='bold' if primary else 'normal'))
 def apply_theme(self):
  ctk.set_appearance_mode(self.theme);p=self.colors();self.root.configure(fg_color=p['bg'])
  self.clear(self.root)
  outer=ctk.CTkFrame(self.root,fg_color='transparent');outer.pack(fill='both',expand=True,padx=23,pady=(17,18))
  head=ctk.CTkFrame(outer,fg_color='transparent',height=85);head.pack(fill='x');head.pack_propagate(False)
  head.bind('<ButtonPress-1>',self.drag_start);head.bind('<B1-Motion>',self.drag_move)
  logo=self.label(head,'',size=12);logo.configure(image=self.logo,width=47,height=75);logo.pack(side='left',padx=(0,13))
  title=ctk.CTkFrame(head,fg_color='transparent');title.pack(side='left',fill='y')
  name=self.label(title,'Horde Watcher',23,True);name.pack(anchor='w',pady=(11,0));sub=self.label(title,self.t('subtitle'),12,color=p['muted']);sub.pack(anchor='w')
  for w in (title,name,sub,logo):w.bind('<ButtonPress-1>',self.drag_start);w.bind('<B1-Motion>',self.drag_move)
  close=self.button(head,'✕',self.quit,width=33,height=33);close.pack(side='right',padx=(6,0),pady=(13,0))
  mini=self.button(head,'−',self.minimize,width=33,height=33);mini.pack(side='right',pady=(13,0))
  self.langbtn=self.button(head,self.lang.upper(),self.change_language,width=46,height=33);self.langbtn.pack(side='right',padx=(0,8),pady=(13,0))
  theme_icon='☾' if self.effective_theme()=='dark' else '☼'
  self.themebtn=self.button(head,theme_icon,self.cycle_theme,width=39,height=33);self.themebtn.pack(side='right',padx=(0,7),pady=(13,0))
  card=ctk.CTkFrame(outer,fg_color=p['card'],corner_radius=16);card.pack(fill='x',pady=(12,12))
  row=ctk.CTkFrame(card,fg_color='transparent');row.pack(fill='x',padx=19,pady=(18,4))
  self.dot=self.label(row,'●',20,color=AMBER);self.dot.pack(side='left',padx=(0,10))
  self.state_label=self.label(row,'',17,True);self.state_label.pack(side='left')
  self.interval_label=self.label(row,self.t('every').format(n=self.interval),11,color=p['muted']);self.interval_label.pack(side='right')
  self.platform_frame=ctk.CTkFrame(card,fg_color='transparent');self.platform_frame.pack(fill='x',padx=23,pady=(0,15))
  self.checkbtn=self.button(outer,self.t('check'),self.check,True,height=49);self.checkbtn.pack(fill='x',pady=(0,12))
  actions=ctk.CTkFrame(outer,fg_color='transparent');actions.pack(fill='x')
  for i,(txt,fn) in enumerate([(self.t('settings'),self.show_settings),(self.t('test'),self.test_alert)]):
   actions.grid_columnconfigure(i,weight=1,uniform='actions');self.button(actions,txt,fn,height=39).grid(row=0,column=i,sticky='ew',padx=(0 if i==0 else 6,0))
  recent=ctk.CTkFrame(outer,fg_color='transparent');recent.pack(fill='x',pady=(18,9))
  self.label(recent,self.t('journal'),16,True).pack(side='left')
  self.journal_frame=ctk.CTkScrollableFrame(outer,fg_color=p['card'],corner_radius=14,height=245)
  self.journal_frame.pack(fill='both',expand=True)
  self.foot=self.label(outer,'',11,color=p['muted']);self.foot.pack(anchor='w',pady=(12,0))
  self.refresh()
 def refresh(self):
  if not self.running:return
  if self.busy:state='checking';color=AMBER
  elif self.last is None:state='checking';color=AMBER
  elif self.errors:state='issues';color=AMBER
  else:state='active';color=GREEN
  self.dot.configure(text_color=color);self.state_label.configure(text=self.t(state))
  self.interval_label.configure(text=self.t('every').format(n=self.interval))
  self.foot.configure(text=f"{self.t('last')}: {self.last.strftime('%d.%m %H:%M:%S') if self.last else self.t('never')}    ·    {self.t('notice')}",wraplength=610,justify='left')
  self.clear(self.platform_frame);p=self.colors()
  groups=[('Blizzard EU',['Blizzard EU']),('Reddit',['Reddit · r/wow','Reddit · global'])]
  for label,names in groups:
   failures=[err for name,err in self.errors if name in names]
   known=[name for name,count in self.stats if name in names]
   if not known:status=self.t('waiting');dot=AMBER
   elif failures:status=failures[0] if len(failures)==1 else failures[0]+' (2 requests)';dot=RED
   else:status=self.t('available');dot=GREEN
   line=ctk.CTkFrame(self.platform_frame,fg_color='transparent');line.pack(fill='x',pady=3)
   self.label(line,'●',12,color=dot).pack(side='left',padx=(0,8))
   self.label(line,label,12).pack(side='left')
   self.label(line,status,11,color=p['muted']).pack(side='right')
  self.render_journal()
 def render_journal(self):
  if not hasattr(self,'journal_frame') or not self.journal_frame.winfo_exists():return
  self.clear(self.journal_frame);p=self.colors()
  if not self.logs:
   self.label(self.journal_frame,self.t('noentries'),12,color=p['muted']).pack(pady=22)
  for tm,s,kind in self.logs[-90:][::-1]:
   color=RED if kind=='error' else AMBER if kind=='important' else p['muted']
   row=ctk.CTkFrame(self.journal_frame,fg_color='transparent');row.pack(fill='x',padx=10,pady=3)
   self.label(row,tm,11,color=p['muted'],width=66,anchor='w').pack(side='left',anchor='n')
   lbl=self.label(row,s,12,color=color,wraplength=495,justify='left',anchor='w');lbl.pack(side='left',fill='x',expand=True)
   if kind=='important':
    match=re.search(r'https?://\S+',s)
    if match:
     url=match.group(0);lbl.configure(cursor='hand2');lbl.bind('<Button-1>',lambda e,u=url:webbrowser.open(u))
 def drag_start(self,e):self.drag_x=e.x_root-self.root.winfo_x();self.drag_y=e.y_root-self.root.winfo_y()
 def drag_move(self,e):self.root.geometry(f'+{e.x_root-self.drag_x}+{e.y_root-self.drag_y}')
 def register_taskbar(self):
  """Register frameless root with Windows taskbar and Alt+Tab."""
  if not self.running or not self.root.winfo_exists() or os.name!='nt':return
  try:
   user32=ctypes.windll.user32
   hwnd=user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
   get_style=user32.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p)==8 else user32.GetWindowLongW
   set_style=user32.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p)==8 else user32.SetWindowLongW
   get_style.argtypes=[ctypes.c_void_p,ctypes.c_int];get_style.restype=ctypes.c_ssize_t
   set_style.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_ssize_t];set_style.restype=ctypes.c_ssize_t
   current=get_style(hwnd,-20)
   target=(current & ~0x80)|0x40000
   if current!=target:
    set_style(hwnd,-20,target)
    user32.ShowWindow(ctypes.c_void_p(hwnd),0)
    user32.ShowWindow(ctypes.c_void_p(hwnd),5)
  except (OSError,AttributeError,tk.TclError) as exc:
   self.logline('Taskbar integration: '+str(exc),'error')
 def minimize(self):
  if not self.running:return
  self.root.overrideredirect(False)
  self.root.iconify()
 def on_map(self,event):
  if event.widget is self.root and self.running:
   self.root.after(120,self.restore_frameless)
 def restore_frameless(self):
  if not self.running or not self.root.winfo_exists() or self.root.state()!='normal':return
  if not self.root.overrideredirect():self.root.overrideredirect(True)
  self.register_taskbar()
 def change_language(self):self.lang='en' if self.lang=='ru' else 'ru';self.save();self.root.after_idle(self.apply_theme)
 def cycle_theme(self):self.theme='light' if self.theme=='dark' else 'dark';self.save();self.root.after_idle(self.apply_theme)
 def tick(self):
  if not self.running:return
  if time.monotonic()>=self.next_check and not self.busy:self.check()
  self.root.after(1000,self.tick)
 def check(self):
  if self.busy or not self.running:return
  self.busy=True;self.refresh();threading.Thread(target=self.worker,daemon=True).start()
 def worker(self):
  result=collect()
  try:self.root.after(0,lambda:self.finish(*result))
  except RuntimeError:pass
 def logline(self,s,kind='normal'):
  self.logs.append((datetime.now().strftime('%H:%M:%S'),s,kind));self.logs=self.logs[-500:]
 def finish(self,posts,errors,stats):
  if not self.running:return
  self.busy=False;self.last=datetime.now();self.errors=errors;self.stats=stats;self.next_check=time.monotonic()+self.interval*60
  new=[]
  for src,uid,title,body,url,ts in posts:
   if uid not in self.seen and candidate(title,body):new.append({'source':src,'title':title,'url':url,'time':self.last.strftime('%d.%m %H:%M')})
   self.seen.add(uid)
  SEEN.write_text(json.dumps(list(self.seen)[-3000:]),encoding='utf-8')
  for src,count in stats:self.logline(f'{src}: {count} '+('публикаций' if self.lang=='ru' else 'posts'))
  for src,err in errors:self.logline(f'{self.t("error")}: {src} · {err}','error')
  if self.first:self.logline(self.t('first'));self.first=False
  else:
   for ev in new:
    self.events.insert(0,ev);self.logline(self.t('unverified')+': '+ev['title']+' · '+ev['url'],'important');self.alert(ev)
   if not new:self.logline(self.t('none'))
  self.refresh()
 def show_log(self):
  w=self.popup(self.t('log'),710,525);p=self.colors()
  panel=ctk.CTkScrollableFrame(w,fg_color=p['card'],corner_radius=12);panel.pack(fill='both',expand=True,padx=19,pady=(0,16))
  for tm,s,kind in self.logs[-150:]:
   color=RED if kind=='error' else AMBER if kind=='important' else p['muted']
   self.label(panel,f'[{tm}]  {s}',12,color=color,wraplength=630,justify='left').pack(anchor='w',fill='x',padx=10,pady=3)
  if not self.logs:self.label(panel,self.t('empty'),12).pack(pady=20)
 def show_settings(self):
  w=self.popup(self.t('settings'),410,345);p=self.colors()
  body=ctk.CTkFrame(w,fg_color='transparent');body.pack(fill='both',expand=True,padx=22)
  self.label(body,self.t('lang'),13).pack(anchor='w',pady=(7,4))
  lang=ctk.CTkSegmentedButton(body,values=['RU','EN'],command=lambda v:self.set_lang(v.lower()),selected_color=ACCENT,selected_hover_color='#9B4B57');lang.pack(fill='x');lang.set(self.lang.upper())
  self.label(body,self.t('theme'),13).pack(anchor='w',pady=(14,4))
  themes=ctk.CTkSegmentedButton(body,values=['Dark','Light'],command=lambda v:self.set_theme(v.lower()),selected_color=ACCENT,selected_hover_color='#9B4B57');themes.pack(fill='x');themes.set(self.theme.capitalize())
  self.label(body,self.t('interval'),13).pack(anchor='w',pady=(14,4))
  intervals=ctk.CTkSegmentedButton(body,values=['2','5','10','15','30'],command=self.set_interval,selected_color=ACCENT,selected_hover_color='#9B4B57');intervals.pack(fill='x');intervals.set(str(self.interval))
  self.label(body,self.t('saved'),11,color=p['muted']).pack(anchor='w',pady=15)
 def set_lang(self,v):self.lang=v;self.save();self.close_popup();self.root.after_idle(self.apply_theme)
 def set_theme(self,v):self.theme=v;self.save();self.close_popup();self.root.after_idle(self.apply_theme)
 def set_interval(self,v):self.interval=int(v);self.next_check=time.monotonic()+self.interval*60;self.save();self.refresh()
 def popup(self,title,width,height):
  self.close_popup();p=self.colors();w=ctk.CTkToplevel(self.root);self.modal=w;w.title(title);w.geometry(f'{width}x{height}+{self.root.winfo_x()+30}+{self.root.winfo_y()+30}');w.configure(fg_color=p['bg']);w.attributes('-topmost',True)
  top=ctk.CTkFrame(w,fg_color='transparent');top.pack(fill='x',padx=20,pady=(17,12));self.label(top,title,18,True).pack(side='left');self.button(top,'✕',self.close_popup,width=34,height=31).pack(side='right')
  w.protocol('WM_DELETE_WINDOW',self.close_popup);return w
 def close_popup(self):
  if self.modal is not None:
   try:self.modal.destroy()
   except tk.TclError:pass
   self.modal=None
 def alert(self,ev=None):
  try:winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
  except RuntimeError:pass
  w=self.popup(self.t('testhead') if ev is None else self.t('unverified'),510,245)
  msg=self.t('testbody') if ev is None else ev['title']+'\n\n'+self.t('report')
  self.label(w,msg,13,wraplength=460,justify='left').pack(fill='x',padx=23,pady=14)
  if ev:self.button(w,self.t('open'),lambda:webbrowser.open(ev['url']),True).pack(pady=4)
  else:self.button(w,self.t('ok'),self.close_popup,True).pack(pady=4)
  self.root.deiconify();self.root.lift()
 def test_alert(self):self.alert()
 def quit(self):self.running=False;self.close_popup();self.root.destroy()
 def run(self):self.root.mainloop()

if __name__=='__main__':
 try:App().run()
 except Exception:
  write_error('Startup', *sys.exc_info())
  raise
