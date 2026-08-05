import sys
import os

# Correção obrigatória para o erro do PyInstaller no modo invisível (--windowed)
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

import tkinter as tk
from tkinter import ttk
import threading
import time
import speedtest
import requests
import xml.etree.ElementTree as ET
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
from plyer import notification

class MonitorApp:
    def __init__(self):
        # Configuração da Janela Principal
        self.root = tk.Tk()
        self.root.title("Monitor de Rede")
        self.root.geometry("380x250")
        self.root.resizable(False, False)
        
        # Quando clicar no 'X', a janela esconde em vez de fechar
        self.root.protocol('WM_DELETE_WINDOW', self.esconder_janela)

        # Criando as Abas
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both', padx=10, pady=10)

        # --- ABA 1: SpeedTest ---
        self.tab_st = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_st, text="SpeedTest")

        self.lbl_st_isp = ttk.Label(self.tab_st, text="Provedor (SpeedTest): Identificando...", font=("Arial", 10, "bold"))
        self.lbl_st_isp.pack(pady=15)

        # Botão para teste sob demanda
        self.btn_test = ttk.Button(self.tab_st, text="Realizar Teste de Velocidade", command=self.iniciar_teste_velocidade)
        self.btn_test.pack(pady=5)

        self.lbl_st_result = ttk.Label(self.tab_st, text="")
        self.lbl_st_result.pack(pady=5)

        # --- ABA 2: IP-API ---
        self.tab_api = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_api, text="Provedor")

        self.lbl_api_isp = ttk.Label(self.tab_api, text="Provedor (IP-API): Identificando...", font=("Arial", 10, "bold"))
        self.lbl_api_isp.pack(pady=20)
        
        self.lbl_api_status = ttk.Label(self.tab_api, text="Esta API apenas verifica a rota\nde forma ultra leve e em tempo real.", justify="center")
        self.lbl_api_status.pack()

        # --- RODAPÉ (Assinatura) ---
        rodape = tk.Label(self.root, text="Desenvolvido por Matheus Carvalho", font=("Arial", 4), fg="gray")
        rodape.pack(side="bottom", pady=5)

        self.provedor_atual = None
        
        # Inicia o monitoramento oculto em segundo plano
        threading.Thread(target=self.monitorar_loop, daemon=True).start()

    def esconder_janela(self):
        self.root.withdraw()

    def mostrar_janela(self):
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)

    def iniciar_teste_velocidade(self):
        self.btn_test.config(state="disabled")
        self.lbl_st_result.config(text="Testando velocidade... Aguarde (pode levar 30s)")
        threading.Thread(target=self.executar_teste_velocidade, daemon=True).start()

    def executar_teste_velocidade(self):
        try:
            st = speedtest.Speedtest(secure=True)
            st.get_best_server()
            download = st.download() / 1_000_000
            upload = st.upload() / 1_000_000
            ping = st.results.ping
            
            resultado = f"Ping: {ping:.0f} ms | Down: {download:.1f} Mbps | Up: {upload:.1f} Mbps"
            self.root.after(0, lambda: self.lbl_st_result.config(text=resultado))
        except Exception:
            self.root.after(0, lambda: self.lbl_st_result.config(text="Falha ao testar. Verifique a conexão."))
        finally:
            self.root.after(0, lambda: self.btn_test.config(state="normal"))

    def monitorar_loop(self):
        while True:
            # 1. Consulta ultraleve no SpeedTest (apenas lê o nome da rede, sem testes)
            try:
                r_st = requests.get("https://www.speedtest.net/speedtest-config.php", timeout=5)
                root = ET.fromstring(r_st.content)
                cliente = root.find('client')
                prov_st = cliente.attrib.get('isp', "Desconhecido") if cliente is not None else "Desconhecido"
            except Exception:
                prov_st = "Sem Conexão"

            # 2. Consulta ultraleve na IP-API
            try:
                r_api = requests.get("http://ip-api.com/json/", timeout=5)
                prov_api = r_api.json().get('isp', "Desconhecido")
            except Exception:
                prov_api = "Sem Conexão"

            # Atualiza os textos da interface imediatamente
            self.root.after(0, lambda p=prov_st: self.lbl_st_isp.config(text=f"Provedor (SpeedTest): {p}"))
            self.root.after(0, lambda p=prov_api: self.lbl_api_isp.config(text=f"Provedor (IP-API): {p}"))

            # Notificação no relógio em caso de queda e troca
            if prov_st != "Sem Conexão" and prov_st != self.provedor_atual:
                if self.provedor_atual is not None:
                    notification.notify(
                        title="Troca de Provedor!",
                        message=f"Conexão alterada para: {prov_st}",
                        app_name="Monitor de Rede",
                        timeout=5
                    )
                self.provedor_atual = prov_st
            
            # Aguarda 30 segundos
            time.sleep(30)

def criar_icone():
    imagem = Image.new('RGB', (64, 64), color=(30, 30, 30))
    desenho = ImageDraw.Draw(imagem)
    desenho.ellipse((16, 16, 48, 48), fill=(0, 120, 255))
    return imagem

def iniciar_bandeja(app):
    def on_abrir(icon, item):
        app.mostrar_janela()

    def on_sair(icon, item):
        icon.stop()
        app.root.quit()
        sys.exit()

    menu = Menu(
        MenuItem("Abrir Painel", on_abrir, default=True),
        MenuItem("Sair", on_sair)
    )
    icone = Icon("MonitorRede", criar_icone(), menu=menu)
    icone.run()

if __name__ == '__main__':
    app = MonitorApp()
    app.esconder_janela()
    
    thread_tray = threading.Thread(target=iniciar_bandeja, args=(app,), daemon=True)
    thread_tray.start()
    
    app.root.mainloop()
