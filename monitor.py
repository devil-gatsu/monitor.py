import sys
import os

# Correção para rodar invisível
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
import socket

# --- FUNÇÕES DE MELHORIA E LEVEZA ---

def limpar_nome_provedor(nome_bruto):
    """Traduz a razão social para o nome comercial da marca"""
    nome = nome_bruto.upper()
    if "TELEF" in nome or "VIVO" in nome:
        return "Vivo"
    elif "CLARO" in nome or "NET" in nome or "EMBRATEL" in nome:
        return "Claro"
    elif "ALLREDE" in nome:
        return "Allrede Telecom"
    # Se for outro provedor, ajusta para as primeiras palavras ficarem bonitas
    return nome_bruto.title()

def checar_latencia_leve():
    """Faz um ping minúsculo para medir instabilidade sem pesar a rede"""
    inicio = time.time()
    try:
        # Conecta no DNS do Google (timeout de 2 segundos)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            s.connect(("8.8.8.8", 53))
    except Exception:
        return 9999 # Sinal de queda ou muita lentidão
    fim = time.time()
    return int((fim - inicio) * 1000) # Retorna em milissegundos


class MonitorApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Monitor de Rede")
        self.root.geometry("400x300")
        self.root.resizable(False, False)
        self.root.protocol('WM_DELETE_WINDOW', self.esconder_janela)

        # Aplicando um tema mais moderno e limpo
        style = ttk.Style()
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        
        style.configure("TLabel", background="#f0f0f0", font=("Segoe UI", 10))
        style.configure("Titulo.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("TFrame", background="#f0f0f0")
        style.configure("TButton", font=("Segoe UI", 10), padding=5)
        
        self.root.configure(bg="#f0f0f0")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both', padx=15, pady=15)

        # --- ABA 1: Provedor e Ping ---
        self.tab_st = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_st, text=" Status da Conexão ")

        self.lbl_provedor = ttk.Label(self.tab_st, text="Provedor: Identificando...", style="Titulo.TLabel", foreground="#005a9e")
        self.lbl_provedor.pack(pady=(20, 5))

        self.lbl_estabilidade = ttk.Label(self.tab_st, text="Estabilidade: Medindo...", font=("Segoe UI", 10))
        self.lbl_estabilidade.pack(pady=5)

        self.btn_test = ttk.Button(self.tab_st, text="Executar Teste Completo de Velocidade", command=self.iniciar_teste_velocidade)
        self.btn_test.pack(pady=(15, 5))

        self.lbl_st_result = ttk.Label(self.tab_st, text="")
        self.lbl_st_result.pack(pady=5)

        # --- ABA 2: Sobre a API ---
        self.tab_api = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_api, text=" Diagnóstico API ")

        texto_api = (
            "As informações são cruzadas usando duas fontes:\n"
            "1. SpeedTest Configuration (Leitura Direta)\n"
            "2. IP-API Routing\n\n"
            "Isso garante dupla checagem ultra leve, sem\n"
            "consumir sua banda de internet no dia a dia."
        )
        self.lbl_api_status = ttk.Label(self.tab_api, text=texto_api, justify="center")
        self.lbl_api_status.pack(pady=30)

        # --- RODAPÉ ---
        rodape = tk.Label(self.root, text="Desenvolvido por Matheus Carvalho", font=("Segoe UI", 8), bg="#f0f0f0", fg="gray")
        rodape.pack(side="bottom", pady=5)

        self.provedor_atual = None
        self.rede_estavel = True
        self.primeira_execucao = True
        
        threading.Thread(target=self.monitorar_loop, daemon=True).start()

    def esconder_janela(self):
        self.root.withdraw()

    def mostrar_janela(self):
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)

    def iniciar_teste_velocidade(self):
        self.btn_test.config(state="disabled")
        self.lbl_st_result.config(text="Fazendo download e upload... (aprox. 30s)")
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
            # Identifica provedor primário
            try:
                r_st = requests.get("https://www.speedtest.net/speedtest-config.php", timeout=5)
                root = ET.fromstring(r_st.content)
                cliente = root.find('client')
                prov_bruto = cliente.attrib.get('isp', "Desconhecido") if cliente is not None else "Desconhecido"
            except Exception:
                try:
                    # Fonte redundante caso o speedtest bloqueie a leitura rápida
                    r_api = requests.get("http://ip-api.com/json/", timeout=5)
                    prov_bruto = r_api.json().get('isp', "Desconhecido")
                except Exception:
                    prov_bruto = "Sem Conexão"

            provedor = limpar_nome_provedor(prov_bruto)
            
            # Checagem leve de estabilidade (ping TCP)
            latencia = checar_latencia_leve()
            status_estabilidade = "Estável"
            cor_estabilidade = "green"
            
            if latencia > 300: # Se o ping for maior que 300ms, a rede está engasgando
                status_estabilidade = "Instável / Lenta"
                cor_estabilidade = "red"
            elif latencia == 9999:
                status_estabilidade = "Sem Conexão"
                cor_estabilidade = "red"

            # Atualiza interface
            self.root.after(0, lambda p=provedor: self.lbl_provedor.config(text=f"Provedor: {p}"))
            self.root.after(0, lambda s=status_estabilidade, l=latencia: self.lbl_estabilidade.config(
                text=f"Status: {s} (Latência: {'--' if l==9999 else l} ms)", foreground=cor_estabilidade))

            # Notificação Inicial para confirmar que está funcionando
            if self.primeira_execucao and provedor != "Sem Conexão":
                notification.notify(
                    title="Monitor Ativo",
                    message=f"Rodando em segundo plano. Conectado via {provedor}.",
                    app_name="Monitor de Rede",
                    timeout=5
                )
                self.primeira_execucao = False
                self.provedor_atual = provedor

            # Notificação de Troca de Provedor
            if provedor != "Sem Conexão" and provedor != "Desconhecido" and self.provedor_atual is not None:
                if provedor != self.provedor_atual:
                    notification.notify(
                        title="Troca de Provedor Detectada!",
                        message=f"Sua conexão mudou para: {provedor}",
                        app_name="Monitor de Rede",
                        timeout=5
                    )
                    self.provedor_atual = provedor
            
            # Notificação de Instabilidade Severa
            estavel_agora = (latencia <= 300)
            if self.rede_estavel and not estavel_agora and provedor != "Sem Conexão":
                notification.notify(
                    title="Aviso de Instabilidade",
                    message=f"A conexão via {provedor} está apresentando lentidão.",
                    app_name="Monitor de Rede",
                    timeout=5
                )
            elif not self.rede_estavel and estavel_agora:
                # Avisa quando normalizar
                notification.notify(
                    title="Conexão Normalizada",
                    message=f"A rede do provedor {provedor} voltou à estabilidade.",
                    app_name="Monitor de Rede",
                    timeout=5
                )
            
            self.rede_estavel = estavel_agora

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
