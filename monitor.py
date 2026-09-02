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

ARQUIVO_LOG = "auditoria_rede.txt"

def registrar_log(mensagem):
    try:
        agora = time.strftime("%d/%m/%Y %H:%M:%S")
        with open(ARQUIVO_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{agora}] {mensagem}\n")
    except Exception:
        pass

def abrir_log():
    if os.path.exists(ARQUIVO_LOG):
        os.startfile(ARQUIVO_LOG)
    else:
        registrar_log("=== ARQUIVO DE LOG CRIADO ===")
        os.startfile(ARQUIVO_LOG)

def limpar_nome_provedor(nome_bruto):
    nome = nome_bruto.upper()
    if "TELEF" in nome or "VIVO" in nome: return "Vivo"
    elif "CLARO" in nome or "NET" in nome or "EMBRATEL" in nome: return "Claro"
    elif "ALLREDE" in nome: return "Allrede Telecom"
    return nome_bruto.title()

def checar_latencia_ip(ip="8.8.8.8", porta=53):
    inicio = time.time()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            s.connect((ip, porta))
    except Exception:
        return 9999
    return int((time.time() - inicio) * 1000)

# --- INTERFACE GRÁFICA (DASHBOARD FUNCIONAL) ---

class MonitorApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Monitor de Rede")
        self.root.geometry("360x220") # Tamanho compacto mantido
        self.root.resizable(False, False)
        self.root.protocol('WM_DELETE_WINDOW', self.esconder_janela)

        # Paleta de Cores Dashboard
        COR_FUNDO = "#F8F9FA"
        COR_CARTAO = "#FFFFFF"
        self.COR_TEXTO = "#212529"
        self.COR_SECUNDARIA = "#6C757D"
        self.COR_SUCESSO = "#198754"
        self.COR_ALERTA = "#DC3545"
        self.COR_ATENCAO = "#FFC107"
        
        self.root.configure(bg=COR_FUNDO)

        style = ttk.Style()
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        style.configure("TButton", font=("Segoe UI", 9), padding=5)

        self.card = tk.Frame(self.root, bg=COR_CARTAO, highlightbackground="#DEE2E6", highlightthickness=1)
        self.card.pack(expand=True, fill='both', padx=12, pady=12)

        # LINHA 1: Cabeçalho funcional
        cabecalho = tk.Frame(self.card, bg=COR_CARTAO)
        cabecalho.pack(fill='x', padx=15, pady=(15, 5))
        
        self.lbl_icone = tk.Label(cabecalho, text="⚫", font=("Segoe UI", 14), bg=COR_CARTAO, fg=self.COR_SECUNDARIA)
        self.lbl_icone.pack(side="left")
        
        self.lbl_status_geral = tk.Label(cabecalho, text="Aguardando...", font=("Segoe UI", 11, "bold"), bg=COR_CARTAO, fg=self.COR_TEXTO)
        self.lbl_status_geral.pack(side="left", padx=5)

        # LINHA 2: Detalhes da rede
        detalhes = tk.Frame(self.card, bg=COR_CARTAO)
        detalhes.pack(fill='x', padx=15, pady=5)
        
        self.lbl_provedor = tk.Label(detalhes, text="Provedor: --", font=("Segoe UI", 10), bg=COR_CARTAO, fg=self.COR_SECUNDARIA)
        self.lbl_provedor.pack(anchor="w")
        
        self.lbl_latencia = tk.Label(detalhes, text="Latência: -- ms", font=("Segoe UI", 10), bg=COR_CARTAO, fg=self.COR_SECUNDARIA)
        self.lbl_latencia.pack(anchor="w")

        separador = tk.Frame(self.card, bg="#E9ECEF", height=1)
        separador.pack(fill='x', padx=15, pady=10)

        # LINHA 3: Botões e Teste
        botoes = tk.Frame(self.card, bg=COR_CARTAO)
        botoes.pack(fill='x', padx=15)
        
        self.btn_log = ttk.Button(botoes, text="📄 Abrir Log", command=abrir_log, width=12)
        self.btn_log.pack(side="left", padx=(0, 5))

        self.btn_test = ttk.Button(botoes, text="⚡ Teste de Velocidade", command=self.iniciar_teste_velocidade)
        self.btn_test.pack(side="left")

        self.lbl_st_result = tk.Label(self.card, text="", font=("Segoe UI", 9, "bold"), bg=COR_CARTAO, fg="#0D6EFD")
        self.lbl_st_result.pack(pady=(10, 0))

        rodape = tk.Label(self.root, text="Desenvolvido por Matheus Carvalho", font=("Segoe UI", 7), bg=COR_FUNDO, fg="#ADB5BD")
        rodape.pack(side="bottom", pady=2)

        # Variáveis de Estado (Máquina de Estados)
        self.provedor_atual = "Desconhecido"
        self.estado_atual = "INICIANDO" # Pode ser: NORMAL, LENTA, CAIDA
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
        self.lbl_st_result.config(text="Testando rede... Aguarde.")
        threading.Thread(target=self.executar_teste_velocidade, daemon=True).start()

    def executar_teste_velocidade(self):
        try:
            st = speedtest.Speedtest(secure=True)
            st.get_best_server()
            res = f"Down: {(st.download()/1_000_000):.1f} Mbps | Up: {(st.upload()/1_000_000):.1f} Mbps"
            self.root.after(0, lambda: self.lbl_st_result.config(text=res))
        except Exception:
            self.root.after(0, lambda: self.lbl_st_result.config(text="Falha no teste."))
        finally:
            self.root.after(0, lambda: self.btn_test.config(state="normal"))

    def monitorar_loop(self):
        while True:
            # 1. Identificação do Provedor
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
            
            # 2. Medição (Gatilho ajustado para 150ms)
            latencia = checar_latencia_ip("8.8.8.8", 53)
            
            # 3. Definição do Estado da Rede
            if latencia == 9999 or provedor == "Sem Conexão":
                novo_estado = "CAIDA"
                provedor = "Sem Conexão"
            elif latencia > 150:
                novo_estado = "LENTA"
            else:
                novo_estado = "NORMAL"

            # IGNORAR ALERTAS NA PRIMEIRA LEITURA
            if self.primeira_execucao:
                self.estado_atual = novo_estado
                self.provedor_atual = provedor
                self.primeira_execucao = False
                if provedor != "Sem Conexão":
                    notification.notify(title="Monitor Ativo", message=f"Conectado via {provedor}.", app_name="Monitor de Rede", timeout=5)
                    registrar_log(f"CONEXÃO INICIAL: Estabelecida através da {provedor}")
            else:
                # LOGICA DE NOTIFICAÇÃO BLINDADA
                
                # A) Caiu a internet
                if novo_estado == "CAIDA" and self.estado_atual != "CAIDA":
                    notification.notify(title="Falha Crítica!", message="A conexão com a internet caiu.", app_name="Monitor", timeout=5)
                    registrar_log("QUEDA TOTAL: Conexão com a internet foi perdida.")
                
                # B) A internet voltou (Reconexão)
                elif novo_estado != "CAIDA" and self.estado_atual == "CAIDA":
                    notification.notify(title="Internet Restaurada", message=f"Reconectado através da {provedor}.", app_name="Monitor", timeout=5)
                    registrar_log(f"RECONEXÃO: Internet reestabelecida via {provedor}.")
                
                # C) Trocou o provedor (Sem queda total percebida)
                elif novo_estado != "CAIDA" and self.estado_atual != "CAIDA" and provedor != self.provedor_atual:
                    notification.notify(title="Mudança de Rota", message=f"O provedor mudou de {self.provedor_atual} para {provedor}.", app_name="Monitor", timeout=5)
                    registrar_log(f"TROCA DE PROVEDOR: Rota alterada de '{self.provedor_atual}' para '{provedor}'.")
                
                # D) Começou a ficar lenta (Acima de 150ms)
                if novo_estado == "LENTA" and self.estado_atual == "NORMAL":
                    notification.notify(title="Instabilidade", message=f"Rede lenta. Latência de {latencia}ms.", app_name="Monitor", timeout=5)
                    registrar_log(f"ALERTA LENTIDÃO: Rota via {provedor} registrou {latencia}ms.")
                
                # E) Voltou a ficar rápida
                elif novo_estado == "NORMAL" and self.estado_atual == "LENTA":
                    notification.notify(title="Rede Normalizada", message="A latência da rede voltou ao normal.", app_name="Monitor", timeout=5)
                    registrar_log(f"RESTAURAÇÃO: A estabilidade do provedor {provedor} voltou ao normal.")

            # Atualizar Interface Visual
            cor_icone = self.COR_ALERTA if novo_estado == "CAIDA" else (self.COR_ATENCAO if novo_estado == "LENTA" else self.COR_SUCESSO)
            icone_txt = "🔴" if novo_estado == "CAIDA" else ("🟡" if novo_estado == "LENTA" else "🟢")
            txt_estado = "Desconectado" if novo_estado == "CAIDA" else ("Instável / Lenta" if novo_estado == "LENTA" else "Conexão Estável")

            self.root.after(0, lambda i=icone_txt, t=txt_estado, c=cor_icone: (self.lbl_icone.config(text=i, fg=c), self.lbl_status_geral.config(text=t)))
            self.root.after(0, lambda p=provedor: self.lbl_provedor.config(text=f"Provedor: {p}"))
            self.root.after(0, lambda l=latencia: self.lbl_latencia.config(text=f"Latência: {'--' if l==9999 else l} ms"))

            # Salvar estado para a próxima rodada
            self.estado_atual = novo_estado
            self.provedor_atual = provedor
            
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
