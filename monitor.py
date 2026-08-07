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

# --- FUNÇÕES DE MELHORIA E LEVEZA --- MELHORIAS 

def limpar_nome_provedor(nome_bruto):
    nome = nome_bruto.upper()
    if "TELEF" in nome or "VIVO" in nome:
        return "Vivo"
    elif "CLARO" in nome or "NET" in nome or "EMBRATEL" in nome:
        return "Claro"
    elif "ALLREDE" in nome:
        return "Allrede Telecom"
    return nome_bruto.title()

def checar_latencia_leve():
    inicio = time.time()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            s.connect(("8.8.8.8", 53))
    except Exception:
        return 9999
    fim = time.time()
    return int((fim - inicio) * 1000)


class MonitorApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Monitor de Rede")
        self.root.geometry("420x340")
        self.root.resizable(False, False)
        self.root.protocol('WM_DELETE_WINDOW', self.esconder_janela)

        # --- PALETA DE CORES SOFT & ELEGANT ---
        COR_FUNDO = "#F4F6F9"       # Off-white cinza azulado suave
        COR_CARTAO = "#FFFFFF"      # Branco puro
        COR_TEXTO_PRINCIPAL = "#2C3E50" # Cinza chumbo escuro (elegante)
        COR_TEXTO_SECUNDARIO = "#7F8C8D" # Cinza suave
        COR_DESTAQUE = "#3498DB"    # Azul limpo e profissional
        COR_SUCESSO = "#27AE60"     # Verde suave
        COR_ALERTA = "#E74C3C"      # Vermelho suave
        
        self.root.configure(bg=COR_FUNDO)

        # Estilo do Botão Flat
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Flat.TButton", 
                        font=("Segoe UI", 10), 
                        background=COR_FUNDO, 
                        foreground=COR_TEXTO_PRINCIPAL,
                        borderwidth=1,
                        bordercolor="#D5DBDB",
                        focuscolor=COR_FUNDO,
                        padding=8)
        style.map("Flat.TButton", background=[('active', '#EAECEE')])

        # --- CONTAINER PRINCIPAL (Efeito de Cartão) ---
        self.card = tk.Frame(self.root, bg=COR_CARTAO, highlightbackground="#E2E6EA", highlightthickness=1)
        self.card.pack(expand=True, fill='both', padx=25, pady=25)

        # Cabeçalho do Cartão
        lbl_titulo = tk.Label(self.card, text="CONEXÃO ATUAL", font=("Segoe UI", 10, "bold"), bg=COR_CARTAO, fg=COR_TEXTO_SECUNDARIO)
        lbl_titulo.pack(pady=(25, 5))

        # Nome do Provedor (O grande destaque)
        self.lbl_provedor = tk.Label(self.card, text="Identificando...", font=("Segoe UI", 24, "bold"), bg=COR_CARTAO, fg=COR_DESTAQUE)
        self.lbl_provedor.pack(pady=5)

        # Status e Latência
        self.lbl_estabilidade = tk.Label(self.card, text="Verificando rota e estabilidade...", font=("Segoe UI", 11), bg=COR_CARTAO, fg=COR_TEXTO_SECUNDARIO)
        self.lbl_estabilidade.pack(pady=(0, 25))

        # Linha separadora discreta
        separador = tk.Frame(self.card, bg="#F0F3F4", height=1)
        separador.pack(fill='x', padx=30, pady=5)

        # Botão e Resultado do Teste
        self.btn_test = ttk.Button(self.card, text="Realizar Teste de Velocidade", style="Flat.TButton", command=self.iniciar_teste_velocidade)
        self.btn_test.pack(pady=(15, 5))

        self.lbl_st_result = tk.Label(self.card, text="", font=("Segoe UI", 10), bg=COR_CARTAO, fg=COR_TEXTO_PRINCIPAL)
        self.lbl_st_result.pack(pady=5)

        # --- RODAPÉ ---
        rodape = tk.Label(self.root, text="Desenvolvido por Matheus Carvalho", font=("Segoe UI", 8), bg=COR_FUNDO, fg="#BDC3C7")
        rodape.pack(side="bottom", pady=8)

        # Variáveis de Controle
        self.provedor_atual = None
        self.rede_estavel = True
        self.primeira_execucao = True
        
        self.COR_SUCESSO = COR_SUCESSO
        self.COR_ALERTA = COR_ALERTA
        self.COR_TEXTO_SECUNDARIO = COR_TEXTO_SECUNDARIO
        
        threading.Thread(target=self.monitorar_loop, daemon=True).start()

    def esconder_janela(self):
        self.root.withdraw()

    def mostrar_janela(self):
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)

    def iniciar_teste_velocidade(self):
        self.btn_test.config(state="disabled")
        self.lbl_st_result.config(text="Fazendo download e upload... (aprox. 30s)", fg=self.COR_TEXTO_SECUNDARIO)
        threading.Thread(target=self.executar_teste_velocidade, daemon=True).start()

    def executar_teste_velocidade(self):
        try:
            st = speedtest.Speedtest(secure=True)
            st.get_best_server()
            download = st.download() / 1_000_000
            upload = st.upload() / 1_000_000
            ping = st.results.ping
            resultado = f"Ping: {ping:.0f} ms  •  Down: {download:.1f} Mbps  •  Up: {upload:.1f} Mbps"
            self.root.after(0, lambda: self.lbl_st_result.config(text=resultado, fg="#2C3E50"))
        except Exception:
            self.root.after(0, lambda: self.lbl_st_result.config(text="Falha ao testar. Verifique a conexão.", fg=self.COR_ALERTA))
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
                    r_api = requests.get("http://ip-api.com/json/", timeout=5)
                    prov_bruto = r_api.json().get('isp', "Desconhecido")
                except Exception:
                    prov_bruto = "Sem Conexão"

            provedor = limpar_nome_provedor(prov_bruto)
            
            # Checagem leve de estabilidade
            latencia = checar_latencia_leve()
            status_estabilidade = "Conexão Estável"
            cor_estabilidade = self.COR_SUCESSO
            
            if latencia > 300:
                status_estabilidade = "Conexão Instável"
                cor_estabilidade = self.COR_ALERTA
            elif latencia == 9999:
                status_estabilidade = "Sem Conexão à Internet"
                cor_estabilidade = self.COR_ALERTA

            # Atualiza interface
            self.root.after(0, lambda p=provedor: self.lbl_provedor.config(text=p, fg="#3498DB" if p != "Sem Conexão" else self.COR_ALERTA))
            self.root.after(0, lambda s=status_estabilidade, l=latencia, c=cor_estabilidade: self.lbl_estabilidade.config(
                text=f"{s} (Latência: {'--' if l==9999 else l} ms)", fg=c))

            # Notificações
            if self.primeira_execucao and provedor != "Sem Conexão":
                notification.notify(
                    title="Monitor Ativo",
                    message=f"Rodando em segundo plano. Conectado via {provedor}.",
                    app_name="Monitor de Rede",
                    timeout=5
                )
                self.primeira_execucao = False
                self.provedor_atual = provedor

            if provedor != "Sem Conexão" and provedor != "Desconhecido" and self.provedor_atual is not None:
                if provedor != self.provedor_atual:
                    notification.notify(
                        title="Troca de Provedor Detectada!",
                        message=f"Sua conexão mudou para: {provedor}",
                        app_name="Monitor de Rede",
                        timeout=5
                    )
                    self.provedor_atual = provedor
            
            estavel_agora = (latencia <= 300)
            if self.rede_estavel and not estavel_agora and provedor != "Sem Conexão":
                notification.notify(
                    title="Aviso de Instabilidade",
                    message=f"A conexão via {provedor} está apresentando lentidão.",
                    app_name="Monitor de Rede",
                    timeout=5
                )
            elif not self.rede_estavel and estavel_agora:
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
