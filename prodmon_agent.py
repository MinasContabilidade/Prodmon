"""
ProdMon Agent v1.3
==================
Monitora atividade de mouse/teclado do usuário de forma silenciosa.

Funcionalidades:
- Detecta períodos ativos, ociosos e bloqueados (lock de tela)
- Registra bloqueio/desbloqueio de sessão em tempo real via WM_WTSSESSION_CHANGE
- Salva dados localmente em JSON por máquina/usuário/dia
- Sincroniza a cada hora com pasta de rede (retry automático)
- Registra boot (session_start) e shutdown (session_end) para apurar jornada
- Grava hostname e usuário logado em cada arquivo
- Rotação automática de logs (RotatingFileHandler)
- Apaga arquivo local após sync bem-sucedido (exceto o do dia atual)
- [DEBUG] Exibe janela ao vivo com cronômetro por estado (debug_mode = true)

Executado via: pythonw.exe prodmon_agent.py   (sem janela/console)
"""

import ctypes
import json
import logging
import logging.handlers
import os
import queue
import shutil
import socket
import sys
import threading
import time
import atexit
import getpass
from datetime import datetime, date, timedelta
from pathlib import Path
import configparser

# ─────────────────────────── Windows API ────────────────────────────────────

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

# GetTickCount64: 64-bit, sem overflow (evita bug após ~49 dias de uptime)
_GetTickCount64 = ctypes.windll.kernel32.GetTickCount64
_GetTickCount64.restype = ctypes.c_ulonglong

# Constantes de sessão Windows
WM_WTSSESSION_CHANGE  = 0x02B1
WTS_SESSION_LOCK      = 7
WTS_SESSION_UNLOCK    = 8
NOTIFY_FOR_THIS_SESSION = 0

def get_idle_seconds() -> float:
    """Retorna segundos desde o último evento de mouse ou teclado."""
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
    elapsed_ms = _GetTickCount64() - lii.dwTime
    return max(0, elapsed_ms) / 1000.0

# ─────────────────────────── Debug Overlay ───────────────────────────────────

class DebugOverlay:
    """
    Janela tkinter always-on-top que exibe ao vivo:
    - Estado atual: ATIVO (verde) / OCIOSO (amarelo) / BLOQUEADO (azul)
    - Cronômetro do tempo no estado atual
    - Totais acumulados do dia (ativo / ocioso / bloqueado)
    - Usuário e máquina identificados
    """

    def __init__(self, agent: "ProdMonAgent"):
        self._agent = agent
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="DebugOverlay"
        )

    def start(self):
        self._thread.start()

    def _fmt(self, seconds: int) -> str:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _run(self):
        try:
            import tkinter as tk
        except ImportError:
            logging.warning("tkinter não disponível — debug overlay desativado.")
            return

        root = tk.Tk()
        root.title("ProdMon Debug")
        root.resizable(False, False)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.93)

        w, h = 270, 170
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f"{w}x{h}+{sw - w - 20}+{sh - h - 60}")

        BG     = "#1e1e2e"
        FG     = "#cdd6f4"
        GREEN  = "#a6e3a1"
        YELLOW = "#f9e2af"
        BLUE   = "#89b4fa"
        GRAY   = "#6c7086"
        FONT_T = ("Consolas", 9, "bold")
        FONT_S = ("Consolas", 13, "bold")
        FONT_C = ("Consolas", 20, "bold")
        FONT_X = ("Consolas", 8)

        root.configure(bg=BG)

        agent = self._agent
        tk.Label(root,
                 text=f"● ProdMon Debug  [{agent.operator_name} · {agent.hostname}]",
                 bg=BG, fg=GRAY, font=FONT_T, anchor="w"
                 ).pack(fill="x", padx=10, pady=(7, 0))

        lbl_state = tk.Label(root, text="ATIVO", bg=BG, fg=GREEN,
                             font=FONT_S, anchor="w")
        lbl_state.pack(fill="x", padx=10, pady=(2, 0))

        lbl_timer = tk.Label(root, text="00:00:00", bg=BG, fg=FG,
                             font=FONT_C, anchor="w")
        lbl_timer.pack(fill="x", padx=10)

        frame = tk.Frame(root, bg=BG)
        frame.pack(fill="x", padx=10, pady=(4, 2))

        lbl_act = tk.Label(frame, text="Ativo    00:00:00",
                           bg=BG, fg=GREEN, font=FONT_X, anchor="w")
        lbl_act.pack(side="left", padx=(0, 8))

        lbl_idl = tk.Label(frame, text="Ocioso   00:00:00",
                           bg=BG, fg=YELLOW, font=FONT_X, anchor="w")
        lbl_idl.pack(side="left", padx=(0, 8))

        lbl_lck = tk.Label(frame, text="Bloqueado 00:00:00",
                           bg=BG, fg=BLUE, font=FONT_X, anchor="w")
        lbl_lck.pack(side="left")

        lbl_start = tk.Label(root, text="Início: --:--", bg=BG, fg=GRAY,
                             font=FONT_X, anchor="w")
        lbl_start.pack(fill="x", padx=10, pady=(0, 6))

        def tick():
            if not agent._running:
                root.destroy()
                return

            with agent._lock:
                state   = agent.current_state
                elapsed = max(0, int((datetime.now() - agent.state_start).total_seconds()))
                act = agent.today_data["summary"].get("active_seconds",  0)
                idl = agent.today_data["summary"].get("idle_seconds",    0)
                lck = agent.today_data["summary"].get("locked_seconds",  0)
                s_start = agent.today_data["summary"].get("session_start", "")

            # Inclui período corrente ainda aberto
            if state == "active":  act += elapsed
            elif state == "idle":  idl += elapsed
            elif state == "locked": lck += elapsed

            COLOR_MAP = {"active": GREEN, "idle": YELLOW, "locked": BLUE}
            TEXT_MAP  = {"active": "● ATIVO", "idle": "● OCIOSO", "locked": "● BLOQUEADO"}

            lbl_state.config(text=TEXT_MAP.get(state, state),
                             fg=COLOR_MAP.get(state, FG))
            lbl_timer.config(text=self._fmt(elapsed))
            lbl_act.config(text=f"Ativo    {self._fmt(act)}")
            lbl_idl.config(text=f"Ocioso   {self._fmt(idl)}")
            lbl_lck.config(text=f"Bloqueado {self._fmt(lck)}")

            if s_start:
                lbl_start.config(text=f"Início da sessão: {s_start[11:16]}")

            root.after(1000, tick)

        tick()
        root.mainloop()


# ─────────────────────────── Agent ──────────────────────────────────────────

class ProdMonAgent:

    # Estados válidos: 'active' | 'idle' | 'locked'
    VALID_STATES = {'active', 'idle', 'locked'}

    def __init__(self, config_path: str):
        self.config   = self._load_config(config_path)
        self.hostname = socket.gethostname().upper()

        # Usuário logado na sessão atual
        try:
            self.username = getpass.getuser()
        except Exception:
            self.username = os.environ.get('USERNAME', os.environ.get('USER', 'desconhecido'))

        self.local_dir   = Path(self.config.get('paths', 'local_dir'))
        self.network_dir = Path(self.config.get('paths', 'network_dir'))

        # Nome do operador (identificação humana para relatórios)
        self.operator_name = (
            self.config.get('user', 'operator_name').strip()
            if self.config.has_option('user', 'operator_name') else ''
        ) or self.username  # fallback: login do Windows

        self.idle_threshold_secs = self.config.getint('settings', 'idle_threshold_minutes') * 60
        self.sync_interval_secs  = self.config.getint('settings', 'sync_interval_minutes')  * 60
        self.check_interval_secs = self.config.getint('settings', 'check_interval_seconds')

        self.debug_mode = (
            self.config.getboolean('debug', 'debug_mode')
            if self.config.has_option('debug', 'debug_mode') else False
        )

        # Garantir diretórios locais
        (self.local_dir / 'data').mkdir(parents=True, exist_ok=True)
        (self.local_dir / 'logs').mkdir(parents=True, exist_ok=True)

        self._setup_logging()
        self._write_pid()

        self._lock             = threading.Lock()
        self._running          = True
        self._shutdown_called  = False

        # Fila de eventos de sessão (produzida pelo MsgPump, consumida no loop principal)
        self._session_queue: queue.Queue = queue.Queue()

        # Estado atual da sessão
        self.current_state = 'active'
        self.state_start   = datetime.now()
        self.today_data    = self._load_or_create_daily_data()

        atexit.register(self._atexit_handler)

        logging.info(
            f"ProdMon v1.3 iniciado | Host: {self.hostname} | "
            f"Operador: {self.operator_name} | Usuário: {self.username}"
        )
        logging.info(
            f"Ociosidade: {self.idle_threshold_secs}s | "
            f"Sync: {self.sync_interval_secs}s | "
            f"Check: {self.check_interval_secs}s | "
            f"Debug: {self.debug_mode}"
        )

    # ── Config ────────────────────────────────────────────────────────────────

    def _load_config(self, path: str) -> configparser.ConfigParser:
        cfg = configparser.ConfigParser()
        if not cfg.read(path, encoding='utf-8'):
            raise FileNotFoundError(f"config.py não encontrado: {path}")
        return cfg

    # ── Logging ───────────────────────────────────────────────────────────────

    def _setup_logging(self):
        log_file = self.local_dir / 'logs' / 'prodmon.log'
        handler  = logging.handlers.RotatingFileHandler(
            filename=str(log_file),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding='utf-8',
        )
        handler.setFormatter(logging.Formatter(
            fmt='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        ))
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(handler)

        if sys.stdout and getattr(sys.stdout, 'isatty', lambda: False)():
            console = logging.StreamHandler(sys.stdout)
            console.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
            root_logger.addHandler(console)

    # ── PID ───────────────────────────────────────────────────────────────────

    def _check_already_running(self):
        """Verifica se já existe outra instância do agente rodando."""
        pid_file = self.local_dir / 'prodmon.pid'
        if not pid_file.exists():
            return
        try:
            old_pid = int(pid_file.read_text().strip())
            if old_pid == os.getpid():
                return
            # Verifica se o processo ainda está vivo
            os.kill(old_pid, 0)  # signal 0 = checa existência
            # Se chegou aqui, o processo está vivo → abortar
            logging.warning(
                f"Outra instância já está rodando (PID {old_pid}). Encerrando."
            )
            sys.exit(0)
        except (ValueError, ProcessLookupError, PermissionError):
            # PID inválido, processo morto, ou sem permissão (considerar morto)
            pass
        except OSError:
            pass

    def _write_pid(self):
        self._check_already_running()
        try:
            (self.local_dir / 'prodmon.pid').write_text(str(os.getpid()))
        except Exception:
            pass

    def _clear_pid(self):
        try:
            pid_file = self.local_dir / 'prodmon.pid'
            if pid_file.exists():
                pid_file.unlink()
        except Exception:
            pass

    # ── Data helpers ──────────────────────────────────────────────────────────

    def _data_file(self, for_date: date = None) -> Path:
        d = for_date or date.today()
        return self.local_dir / 'data' / f"{self.hostname}_{d.strftime('%Y-%m-%d')}.json"

    def _make_daily_data(self, now: datetime) -> dict:
        """Cria estrutura de dados para um novo dia."""
        return {
            "machine":       self.hostname,
            "operator_name": self.operator_name,
            "username":      self.username,
            "date":          now.date().isoformat(),
            "version":       "1.3",
            "events":   [
                {
                    "type":      "boot",
                    "timestamp": now.isoformat(timespec='seconds'),
                }
            ],
            "summary": {
                "active_seconds":  0,
                "idle_seconds":    0,
                "locked_seconds":  0,
                "session_start":   now.isoformat(timespec='seconds'),
                "session_end":     None,
            },
        }

    def _load_or_create_daily_data(self) -> dict:
        f = self._data_file()
        if f.exists():
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)

                # Retrocompatibilidade: garante campos novos se faltarem
                data.setdefault('username', self.username)
                data.setdefault('operator_name', self.operator_name)
                data['summary'].setdefault('locked_seconds', 0)
                if 'session_start' not in data['summary']:
                    boot = next((e for e in data['events'] if e['type'] == 'boot'), None)
                    data['summary']['session_start'] = (
                        boot['timestamp'] if boot else datetime.now().isoformat(timespec='seconds')
                    )
                data['summary'].setdefault('session_end', None)

                logging.info(f"Carregado arquivo existente: {f.name}")
                return data
            except Exception as e:
                logging.warning(f"Não foi possível ler {f.name}: {e} — criando novo.")

        data = self._make_daily_data(datetime.now())
        self._write_data(data)
        return data

    def _write_data(self, data: dict = None):
        """Persiste dados no arquivo local JSON (escrita atômica via tmp + replace)."""
        data = data or self.today_data
        f = self._data_file(date.fromisoformat(data['date']))
        tmp = f.with_suffix('.tmp')
        try:
            with open(tmp, 'w', encoding='utf-8') as fp:
                json.dump(data, fp, indent=2, ensure_ascii=False)
            os.replace(str(tmp), str(f))  # atômico em NTFS
        except Exception as e:
            logging.error(f"Erro ao salvar dados locais: {e}")
            # Limpa arquivo temporário se sobrou
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass

    # ── State recording ───────────────────────────────────────────────────────

    def _record_period(self, state: str, start: datetime, end: datetime):
        """Registra um período de atividade, ociosidade ou bloqueio."""
        duration = int((end - start).total_seconds())
        if duration <= 0:
            return

        event = {
            "type":             state,
            "start":            start.isoformat(timespec='seconds'),
            "end":              end.isoformat(timespec='seconds'),
            "duration_seconds": duration,
        }

        with self._lock:
            self.today_data['events'].append(event)
            key = f"{state}_seconds"
            if key in self.today_data['summary']:
                self.today_data['summary'][key] += duration

        self._write_data()
        logging.debug(
            f"Período {state}: {duration}s "
            f"({start.strftime('%H:%M:%S')} → {end.strftime('%H:%M:%S')})"
        )

    # ── Session lock / unlock handlers ────────────────────────────────────────

    def _handle_session_lock(self, event_time: datetime):
        """Chamado quando a sessão é bloqueada (Win+L, screensaver com senha, etc.)."""
        if self.current_state == 'locked':
            return  # já estava bloqueado

        # Fecha período corrente imediatamente
        self._record_period(self.current_state, self.state_start, event_time)

        with self._lock:
            self.today_data['events'].append({
                "type":      "lock",
                "timestamp": event_time.isoformat(timespec='seconds'),
            })
            self.current_state = 'locked'
            self.state_start   = event_time

        self._write_data()
        logging.info(f"→ BLOQUEADO (tela travada às {event_time.strftime('%H:%M:%S')})")

    def _handle_session_unlock(self, event_time: datetime):
        """Chamado quando a sessão é desbloqueada (usuário voltou)."""
        if self.current_state == 'locked':
            self._record_period('locked', self.state_start, event_time)

        with self._lock:
            self.today_data['events'].append({
                "type":      "unlock",
                "timestamp": event_time.isoformat(timespec='seconds'),
            })
            self.current_state = 'active'
            self.state_start   = event_time

        self._write_data()
        logging.info(f"→ DESBLOQUEADO (retornou às {event_time.strftime('%H:%M:%S')})")

    # ── Date rollover ─────────────────────────────────────────────────────────

    def _check_date_rollover(self):
        """Detecta virada de dia (máquinas ligadas à meia-noite)."""
        if date.today().isoformat() == self.today_data['date']:
            return

        logging.info("Virada de dia detectada.")
        now      = datetime.now()
        midnight = datetime.combine(date.today(), datetime.min.time())

        if self.state_start < midnight:
            self._record_period(self.current_state, self.state_start, midnight)

        self._sync_to_network()

        new_data = self._make_daily_data(now)
        with self._lock:
            self.today_data  = new_data
            self.state_start = now
        self._write_data()

    # ── Network sync ──────────────────────────────────────────────────────────

    def _sync_to_network(self):
        """
        Copia todos os JSONs pendentes para a pasta de rede.
        Apaga o arquivo local após cópia bem-sucedida (exceto o do dia atual).
        """
        try:
            net_dir = self.network_dir / self.hostname
            net_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logging.warning(f"Rede indisponível, sync adiado: {e}")
            return

        today_file = self._data_file()
        data_dir   = self.local_dir / 'data'
        synced, failed = 0, 0

        for f in sorted(data_dir.glob(f"{self.hostname}_*.json")):
            is_today = (f.resolve() == today_file.resolve())
            try:
                dest = net_dir / f.name
                dest_tmp = dest.with_suffix('.tmp')
                shutil.copy2(str(f), str(dest_tmp))
                os.replace(str(dest_tmp), str(dest))
                logging.info(f"Sync OK: {f.name} → {dest}")
                synced += 1
                if not is_today:
                    f.unlink()
                    logging.info(f"Arquivo local removido: {f.name}")
            except Exception as e:
                logging.warning(f"Sync falhou ({f.name}): {e}")
                failed += 1

        if synced or failed:
            logging.info(f"Sync concluído: {synced} enviados, {failed} falharam.")

    def _sync_loop(self):
        while self._running:
            time.sleep(self.sync_interval_secs)
            if self._running:
                logging.info("Sync periódico iniciado.")
                self._sync_to_network()

    # ── Shutdown ──────────────────────────────────────────────────────────────

    def stop(self):
        if self._shutdown_called:
            return
        self._shutdown_called = True
        self._running = False

        logging.info("Encerrando ProdMon Agent...")
        now = datetime.now()

        self._record_period(self.current_state, self.state_start, now)

        with self._lock:
            self.today_data['events'].append({
                "type":      "shutdown",
                "timestamp": now.isoformat(timespec='seconds'),
            })
            # Marca o fim da jornada do dia
            self.today_data['summary']['session_end'] = now.isoformat(timespec='seconds')

        self._write_data()

        logging.info("Tentando sync final antes de desligar...")
        self._sync_to_network()

        self._clear_pid()
        logging.info("ProdMon Agent encerrado.")

    def _atexit_handler(self):
        self.stop()

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        logging.info("Loop principal iniciado.")

        threading.Thread(
            target=self._sync_loop, daemon=True, name="SyncThread"
        ).start()

        if self.debug_mode:
            logging.info("Modo debug ativo — iniciando overlay visual.")
            DebugOverlay(self).start()

        try:
            while self._running:
                time.sleep(self.check_interval_secs)
                if not self._running:
                    break

                # ── 1. Processar eventos de sessão da fila (lock / unlock) ────
                while not self._session_queue.empty():
                    try:
                        ev_type, ev_time = self._session_queue.get_nowait()
                        if ev_type == 'lock':
                            self._handle_session_lock(ev_time)
                        elif ev_type == 'unlock':
                            self._handle_session_unlock(ev_time)
                    except queue.Empty:
                        break

                # ── 2. Verificar virada de dia ────────────────────────────────
                self._check_date_rollover()

                # ── 3. Fallback: polling de lock de sessão (se WTS não disponível) ──
                if self.current_state != 'locked' and _is_session_locked():
                    self._handle_session_lock(datetime.now())
                    continue
                elif self.current_state == 'locked' and not _is_session_locked():
                    self._handle_session_unlock(datetime.now())

                # ── 4. Detecção de ociosidade por input ───────────────────────
                # Não aplica se sessão está bloqueada (lock já cobre o período)
                if self.current_state == 'locked':
                    continue

                idle_secs = get_idle_seconds()
                now       = datetime.now()

                if idle_secs >= self.idle_threshold_secs:
                    # Usuário OCIOSO
                    if self.current_state == 'active':
                        idle_started = max(now - timedelta(seconds=idle_secs), self.state_start)
                        self._record_period('active', self.state_start, idle_started)
                        with self._lock:
                            self.current_state = 'idle'
                            self.state_start   = idle_started
                        logging.info(f"→ OCIOSO (idle há {idle_secs:.0f}s)")
                else:
                    # Usuário ATIVO
                    if self.current_state == 'idle':
                        self._record_period('idle', self.state_start, now)
                        with self._lock:
                            self.current_state = 'active'
                            self.state_start   = now
                        logging.info("→ ATIVO")

        except Exception as e:
            logging.error(f"Erro inesperado no loop principal: {e}", exc_info=True)
        finally:
            self.stop()


# ─────────────────────────── Windows shutdown + session hook ─────────────────

def register_shutdown_hook(agent: ProdMonAgent):
    """
    Cria janela oculta Win32 para capturar:
    - WM_QUERYENDSESSION / WM_ENDSESSION  → desligamento / logoff
    - WM_WTSSESSION_CHANGE                → lock / unlock de sessão (Win+L, screensaver)

    IMPORTANTE: a janela é criada DENTRO da thread MsgPump para que o Win32
    entregue as mensagens na queue correta (thread-affinity do Win32).
    """
    try:
        import win32api
        import win32con
        import win32gui

        def run_message_loop():
            """
            Cria a janela oculta e registra WTS nesta mesma thread.
            Isso garante que WM_WTSSESSION_CHANGE chegue aqui via PumpWaitingMessages.
            """
            try:
                def wnd_proc(hwnd, msg, wparam, lparam):
                    if msg in (win32con.WM_QUERYENDSESSION, win32con.WM_ENDSESSION):
                        logging.info("WM_QUERYENDSESSION / WM_ENDSESSION recebido.")
                        agent.stop()
                        return 1
                    if msg == WM_WTSSESSION_CHANGE:
                        t = datetime.now()
                        if wparam == WTS_SESSION_LOCK:
                            logging.info("WTS_SESSION_LOCK recebido → enfileirando lock.")
                            agent._session_queue.put(('lock', t))
                        elif wparam == WTS_SESSION_UNLOCK:
                            logging.info("WTS_SESSION_UNLOCK recebido → enfileirando unlock.")
                            agent._session_queue.put(('unlock', t))
                        return 0
                    if msg == win32con.WM_DESTROY:
                        win32gui.PostQuitMessage(0)
                        return 0
                    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

                # ── Criação da janela na MESMA thread que irá bombear mensagens ──
                wc               = win32gui.WNDCLASS()
                wc.lpfnWndProc   = wnd_proc
                wc.lpszClassName = "ProdMonHiddenWindow"
                wc.hInstance     = win32api.GetModuleHandle(None)
                win32gui.RegisterClass(wc)
                hwnd = win32gui.CreateWindow(
                    wc.lpszClassName, "ProdMon",
                    0, 0, 0, 0, 0, 0, 0,
                    wc.hInstance, None,
                )

                # Registra WTS no mesmo thread (exigência do Win32)
                try:
                    ctypes.windll.wtsapi32.WTSRegisterSessionNotification(
                        hwnd, NOTIFY_FOR_THIS_SESSION
                    )
                    logging.info("WTS session notification registrada (lock/unlock).")
                except Exception as e:
                    logging.warning(f"WTSRegisterSessionNotification falhou: {e}")

                logging.info("Shutdown hook Win32 ativo (MsgPump thread).")

                # ── Loop de mensagens (processa mensagens da janela criada aqui) ──
                while agent._running:
                    win32gui.PumpWaitingMessages()
                    time.sleep(0.1)

            except Exception as e:
                logging.warning(f"Erro no loop de mensagens Win32: {e}")

        threading.Thread(target=run_message_loop, daemon=True, name="MsgPump").start()

    except ImportError:
        logging.warning(
            "pywin32 não disponível — shutdown hook e session lock não registrados. "
            "Execute: pip install pywin32"
        )
    except Exception as e:
        logging.warning(f"Falha ao registrar shutdown hook: {e}")


def _is_session_locked() -> bool:
    """
    Fallback de polling: verifica se a sessão está bloqueada tentando abrir
    o desktop de entrada. Retorna True se a tela estiver bloqueada (Win+L).

    Usado pelo loop principal como redundância caso o WTS não seja suportado.
    """
    try:
        hdesk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x0100)
        if hdesk:
            ctypes.windll.user32.CloseDesktop(hdesk)
            return False
        return True   # não conseguiu abrir → sessão bloqueada
    except Exception:
        return False



# ─────────────────────────── Entry point ─────────────────────────────────────

def main():
    script_dir  = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).parent
    config_path = script_dir / 'config.py'

    if not config_path.exists():
        config_path = Path(r'C:\ProgramData\ProdMon\config.py')

    if not config_path.exists():
        fallback_log = Path(r'C:\ProgramData\ProdMon\logs\startup_error.txt')
        fallback_log.parent.mkdir(parents=True, exist_ok=True)
        fallback_log.write_text(
            f"[{datetime.now()}] config.py não encontrado em: {config_path}\n"
        )
        return

    agent = ProdMonAgent(str(config_path))
    register_shutdown_hook(agent)
    agent.run()


if __name__ == '__main__':
    main()
