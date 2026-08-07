import sys
import os

# Correção para rodar invisível sem quebrar no Windows
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
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
from plyer import notification
import socket

# --- FUNÇÕES DE LÓGICA E DIAGNÓSTICO ---

def registrar_log(mensagem):
    """Gera o histórico invisível no arquivo TXT"""
    try:
        agora = time.strftime("%d/%m/%Y %H:%M:%S")
        with open("auditoria_rede.txt", "a", encoding="utf-8") as f:
            f.write(f"[{agora}] {mensagem}\n")
    except Exception:
        pass

def limpar_nome_provedor(nome_bruto):
    nome = nome_bruto.upper()
    if "TELEF" in nome or "VIVO" in nome: return "Vivo"
    elif "CLARO" in nome or "NET" in nome or "EMBRATEL" in nome: return "Claro"
    elif "ALLREDE" in nome: return "Allrede Telecom"
    return nome_bruto.title()

def checar_latencia_ip(ip="8.8.8.8", porta=53):
    """Mede o ping via TCP (muito mais leve que o ping do Windows)"""
    inicio = time.time()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            s.connect((ip, porta))
    except Exception:
        return 9999
    return int((time.time() - inicio) * 1000)

def descobrir_ip_roteador():
    """Tenta descobrir o Gateway da empresa para a triagem"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_local = s.getsockname()[0]
        s.close()
        partes = ip_local.split('.')
        partes[-1] = '1'
        return '.'.join(partes)
    except:
        return None

# --- INTERFACE GRÁFICA COMPACTA E SOFT ---

class MonitorApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Monitor de Rede")
        self.root.geometry("350x260") # Tamanho compacto ajustado
        self.root.resizable(False, False)
        self.root.protocol('WM_DELETE_WINDOW', self.esconder_janela)

        # Paleta de Cores
        COR_FUNDO = "#F4F6F9"
        COR_CARTAO = "#FFFFFF"
        self.COR_TEXTO = "#2C3E50"
        self.COR_SECUNDARIA = "#7F8C8D"
        COR_DESTAQUE = "#3498DB"
        self.COR_SUCESSO = "#27AE60"
        self.COR_ALERTA = "#E74C3C"
        
        self.root.configure(bg=COR_FUNDO)

        style = ttk.Style()
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        style.configure("Flat.TButton", font=("Segoe UI", 9), background=COR_FUNDO, foreground=self.COR_TEXTO, borderwidth=1, bordercolor="#D5DBDB", padding=5)
        style.map("Flat.TButton", background=[('active', '#EAECEE')])

        self.card = tk.Frame(self.root, bg=COR_CARTAO, highlightbackground="#E2E6EA", highlightthickness=1)
        self.card.pack(expand=True, fill='both', padx=15, pady=15)

        lbl_titulo = tk.Label(self.card, text="CONEXÃO ATUAL", font=("Segoe UI", 9, "bold"), bg=COR_CARTAO, fg=self.COR_SECUNDARIA)
        lbl_titulo.pack(pady=(15, 0))

        self.lbl_provedor = tk.Label(self.card, text="Iniciando...", font=("Segoe UI", 20, "bold"), bg=COR_CARTAO, fg=COR_DESTAQUE)
        self.lbl_provedor.pack(pady=2)

        self.lbl_estabilidade = tk.Label(self.card, text="Analisando rede...", font=("Segoe UI", 10), bg=COR_CARTAO, fg=self.COR_SECUNDARIA)
        self.lbl_estabilidade.pack(pady=(0, 15))

        separador = tk.Frame(self.card, bg="#F0F3F4", height=1)
        separador.pack(fill='x', padx=20, pady=2)

        self.btn_test = ttk.Button(self.card, text="Teste de Velocidade", style="Flat.TButton", command=self.iniciar_teste_velocidade)
        self.btn_test.pack(pady=(10, 2))

        self.lbl_st_result = tk.Label(self.card, text="", font=("Segoe UI", 9), bg=COR_CARTAO, fg=self.COR_TEXTO)
        self.lbl_st_result.pack(pady=2)

        rodape = tk.Label(self.root, text="Desenvolvido por Matheus Carvalho", font=("Segoe UI", 7), bg=COR_FUNDO, fg="#BDC3C7")
        rodape.pack(side="bottom", pady=4)

        self.provedor_atual = None
        self.rede_estavel = True
        self.primeira_execucao = True
        
        registrar_log("=== MONITOR INICIADO ===")
        threading.Thread(target=self.monitorar_loop, daemon=True).start()

    def esconder_janela(self):
        self.root.withdraw()

    def mostrar_janela(self):
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)

    def iniciar_teste_velocidade(self):
        self.btn_test.config(state="disabled")
        self.lbl_st_result.config(text="Testando... (aprox. 30s)", fg=self.COR_SECUNDARIA)
        threading.Thread(target=self.executar_teste_velocidade, daemon=True).start()

    def executar_teste_velocidade(self):
        try:
            st = speedtest.Speedtest(secure=True)
            st.get_best_server()
            resultado = f"Ping: {st.results.ping:.0f}ms | Down: {(st.download()/1_000_000):.1f}Mbps | Up: {(st.upload()/1_000_000):.1f}Mbps"
            self.root.after(0, lambda: self.lbl_st_result.config(text=resultado, fg=self.COR_TEXTO))
        except Exception:
            self.root.after(0, lambda: self.lbl_st_result.config(text="Falha no teste.", fg=self.COR_ALERTA))
        finally:
            self.root.after(0, lambda: self.btn_test.config(state="normal"))

    def monitorar_loop(self):
        while True:
            # 1. Identificação Oficial Speedtest
            try:
                st = speedtest.Speedtest(secure=True)
                prov_bruto = st.config['client']['isp']
            except Exception:
                try:
                    r_api = requests.get("http://ip-api.com/json/", timeout=5)
                    prov_bruto = r_api.json().get('isp', "Desconhecido")
                except Exception:
                    prov_bruto = "Sem Conexão"

            provedor = limpar_nome_provedor(prov_bruto)
            
            # 2. Triagem de Instabilidade (Internet vs Roteador da Empresa)
            latencia_ext = checar_latencia_ip("8.8.8.8", 53)
            status = "Conexão Estável"
            cor = self.COR_SUCESSO
            
            if latencia_ext > 300 and latencia_ext != 9999:
                ip_roteador = descobrir_ip_roteador()
                latencia_int = checar_latencia_ip(ip_roteador, 80) if ip_roteador else 0
                
                # Se a rede interna também estiver lenta, o problema é local
                if latencia_int > 150 and latencia_int != 9999:
                    status = "Rede Local (Wi-Fi/Roteador) Lenta"
                    cor = self.COR_ALERTA
                else:
                    status = f"Provedor Instável ({latencia_ext}ms)"
                    cor = self.COR_ALERTA
            elif latencia_ext == 9999:
                status = "Sem Conexão"
                cor = self.COR_ALERTA

            # 3. Atualiza Interface
            self.root.after(0, lambda p=provedor, c=self.COR_ALERTA: self.lbl_provedor.config(text=p, fg="#3498DB" if p != "Sem Conexão" else c))
            self.root.after(0, lambda s=status, c=cor: self.lbl_estabilidade.config(text=s, fg=c))

            # 4. Motor de Notificações e Logs
            if self.primeira_execucao and provedor != "Sem Conexão":
                mensagem = f"Monitor rodando via {provedor}."
                notification.notify(title="Monitor Ativo", message=mensagem, app_name="Monitor de Rede", timeout=5)
                registrar_log(f"CONEXÃO INICIAL: Estabelecida através da {provedor}")
                self.primeira_execucao = False
                self.provedor_atual = provedor

            if provedor != "Sem Conexão" and provedor != "Desconhecido" and self.provedor_atual is not None:
                if provedor != self.provedor_atual:
                    aviso = f"Troca detectada! A conexão mudou para: {provedor}"
                    notification.notify(title="Mudança de Rota!", message=aviso, app_name="Monitor", timeout=5)
                    registrar_log(f"TROCA DE PROVEDOR: A rota principal mudou de '{self.provedor_atual}' para '{provedor}'")
                    self.provedor_atual = provedor
            
            estavel_agora = (latencia_ext <= 300)
            if self.rede_estavel and not estavel_agora and provedor != "Sem Conexão":
                notification.notify(title="Instabilidade", message=status, app_name="Monitor", timeout=5)
                registrar_log(f"ALERTA DE LENTIDÃO: {status}")
            elif not self.rede_estavel and estavel_agora:
                notification.notify(title="Rede Normalizada", message=f"A conexão com a {provedor} normalizou.", app_name="Monitor", timeout=5)
                registrar_log(f"RESTAURAÇÃO: A estabilidade do provedor {provedor} voltou ao normal.")
            
            if latencia_ext == 9999 and self.rede_estavel:
                registrar_log("QUEDA TOTAL: Conexão com a internet foi perdida.")
            
            self.rede_estavel = estavel_agora
            time.sleep(30)

def criar_icone():
    imagem = Image.new('RGB', (64, 64), color=(30, 30, 30))
    desenho = ImageDraw.Draw(imagem)
    desenho.ellipse((16, 16, 48, 48), fill=(0, 120, 255))
    return imagem

def iniciar_bandeja(app):
    def on_abrir(icon, item): app.mostrar_janela()
    def on_sair(icon, item):
        registrar_log("=== MONITOR ENCERRADO PELO USUÁRIO ===")
        icon.stop()
        app.root.quit()
        sys.exit()

    menu = Menu(MenuItem("Abrir Painel", on_abrir, default=True), MenuItem("Sair", on_sair))
    Icon("MonitorRede", criar_icone(), menu=menu).run()

if __name__ == '__main__':
    app = MonitorApp()
    app.esconder_janela()
    threading.Thread(target=iniciar_bandeja, args=(app,), daemon=True).start()
    app.root.mainloop()
