import sys
import os

# Correção para rodar invisível sem quebrar no Windows
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import threading
import time
import speedtest
import requests
import xml.etree.ElementTree as ET
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
import socket
import csv
import winreg

# --- CONFIGURAÇÕES DE ARQUIVOS ---
ARQUIVO_TXT = "auditoria_rede.txt"
ARQUIVO_CSV = "auditoria_rede.csv"

# --- FUNÇÕES DE LÓGICA GERAL ---

def registrar_log(evento, provedor="--", ip="--"):
    data = time.strftime("%d/%m/%Y")
    hora = time.strftime("%H:%M:%S")
    
    try:
        with open(ARQUIVO_TXT, "a", encoding="utf-8") as f:
            f.write(f"[{data} {hora}] {evento} | Provedor: {provedor} | IP: {ip}\n")
    except Exception:
        pass

    try:
        arquivo_existe = os.path.exists(ARQUIVO_CSV)
        with open(ARQUIVO_CSV, "a", newline='', encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=';')
            if not arquivo_existe:
                writer.writerow(["Data", "Hora", "Evento", "Provedor", "IP"])
            writer.writerow([data, hora, evento, provedor, ip])
    except Exception:
        pass

def abrir_arquivo(caminho):
    if os.path.exists(caminho):
        os.startfile(caminho)
    else:
        messagebox.showinfo("Aviso", "Nenhum log registrado ainda.")

def configurar_autostart(ativar):
    caminho_exe = sys.executable
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        if ativar:
            winreg.SetValueEx(key, "MonitorRede_Matheus", 0, winreg.REG_SZ, caminho_exe)
        else:
            winreg.DeleteValue(key, "MonitorRede_Matheus")
        winreg.CloseKey(key)
    except Exception:
        pass

def verificar_autostart():
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, "MonitorRede_Matheus")
        winreg.CloseKey(key)
        return True
    except:
        return False

def identificar_provedor_real(dados_raw):
    """
    Identifica de forma estrita entre Vivo e Claro analisando 
    o texto bruto (ISP + Org + AS) retornado.
    """
    texto = (dados_raw or "").upper()
    
    # Marcadores estritos da VIVO / Telefônica
    termos_vivo = ["TELEFONICA", "TELEFÔNICA", "VIVO", "AS27699", "AS18881", "WGO"]
    # Marcadores estritos da CLARO / NET / Embratel
    termos_claro = ["CLARO", "EMBRATEL", "NET VIRTUA", "NET SERVICOS", "AS28573"]

    for t in termos_vivo:
        if t in texto:
            return "Vivo"
            
    for t in termos_claro:
        if t in texto:
            return "Claro"

    if texto.strip() in ("", "DESCONHECIDO", "SEM CONEXÃO"):
        return "Desconhecido"

    return dados_raw.title()

def checar_latencia_ip(ip="8.8.8.8", porta=53):
    inicio = time.time()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            s.connect((ip, porta))
    except Exception:
        return 9999
    return int((time.time() - inicio) * 1000)

# --- INTERFACE GRÁFICA ---

class MonitorApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Monitor de Rede")
        self.root.geometry("380x295")
        self.root.resizable(False, False)
        self.root.protocol('WM_DELETE_WINDOW', self.esconder_janela)

        self.tray_icon = None

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
        style.configure("TButton", font=("Segoe UI", 9), padding=4)

        self.card = tk.Frame(self.root, bg=COR_CARTAO, highlightbackground="#DEE2E6", highlightthickness=1)
        self.card.pack(expand=True, fill='both', padx=12, pady=12)

        # Cabeçalho Status
        cabecalho = tk.Frame(self.card, bg=COR_CARTAO)
        cabecalho.pack(fill='x', padx=15, pady=(12, 4))
        
        self.lbl_icone = tk.Label(cabecalho, text="⚫", font=("Segoe UI", 14), bg=COR_CARTAO, fg=self.COR_SECUNDARIA)
        self.lbl_icone.pack(side="left")
        
        self.lbl_status_geral = tk.Label(cabecalho, text="Iniciando...", font=("Segoe UI", 11, "bold"), bg=COR_CARTAO, fg=self.COR_TEXTO)
        self.lbl_status_geral.pack(side="left", padx=5)

        # Informações de Conexão
        detalhes = tk.Frame(self.card, bg=COR_CARTAO)
        detalhes.pack(fill='x', padx=15, pady=2)
        
        self.lbl_provedor = tk.Label(detalhes, text="Provedor: --", font=("Segoe UI", 10), bg=COR_CARTAO, fg=self.COR_SECUNDARIA)
        self.lbl_provedor.pack(anchor="w")

        self.lbl_ip = tk.Label(detalhes, text="IP Público: --", font=("Segoe UI", 9), bg=COR_CARTAO, fg="#6c757d")
        self.lbl_ip.pack(anchor="w")
        
        self.lbl_latencia = tk.Label(detalhes, text="Latência: -- ms", font=("Segoe UI", 10), bg=COR_CARTAO, fg=self.COR_SECUNDARIA)
        self.lbl_latencia.pack(anchor="w")

        separador = tk.Frame(self.card, bg="#E9ECEF", height=1)
        separador.pack(fill='x', padx=15, pady=8)

        # Botões Principais
        botoes = tk.Frame(self.card, bg=COR_CARTAO)
        botoes.pack(fill='x', padx=15)
        
        self.btn_test = ttk.Button(botoes, text="⚡ Teste de Velocidade", command=self.iniciar_teste_velocidade, width=18)
        self.btn_test.pack(side="left", padx=(0, 5))

        self.btn_resumo = ttk.Button(botoes, text="📈 Resumo Gerencial", command=self.gerar_resumo, width=18)
        self.btn_resumo.pack(side="left")

        ferramentas = tk.Frame(self.card, bg=COR_CARTAO)
        ferramentas.pack(fill='x', padx=15, pady=(8, 0))

        self.btn_txt = ttk.Button(ferramentas, text="📄 TXT", command=lambda: abrir_arquivo(ARQUIVO_TXT), width=6)
        self.btn_txt.pack(side="left", padx=(0, 5))

        self.btn_csv = ttk.Button(ferramentas, text="📊 Excel", command=lambda: abrir_arquivo(ARQUIVO_CSV), width=7)
        self.btn_csv.pack(side="left")

        self.var_autostart = tk.BooleanVar(value=verificar_autostart())
        chk_autostart = tk.Checkbutton(ferramentas, text="Iniciar com Windows", var=self.var_autostart, command=self.toggle_autostart, bg=COR_CARTAO, fg=self.COR_SECUNDARIA, activebackground=COR_CARTAO, selectcolor=COR_CARTAO, font=("Segoe UI", 8))
        chk_autostart.pack(side="right")

        self.lbl_st_result = tk.Label(self.card, text="", font=("Segoe UI", 9, "bold"), bg=COR_CARTAO, fg="#0D6EFD")
        self.lbl_st_result.pack(pady=(4, 0))

        rodape = tk.Label(self.root, text="Desenvolvido por Matheus Carvalho", font=("Segoe UI", 7), bg=COR_FUNDO, fg="#ADB5BD")
        rodape.pack(side="bottom", pady=2)

        self.provedor_atual = "Desconhecido"
        self.ip_atual = "--"
        self.estado_atual = "INICIANDO"
        self.primeira_execucao = True
        
        registrar_log("Monitor Iniciado pelo Usuário")
        threading.Thread(target=self.monitorar_loop, daemon=True).start()

    def enviar_notificacao(self, titulo, mensagem):
        if self.tray_icon is not None:
            try:
                self.tray_icon.notify(mensagem, title=titulo)
            except Exception:
                pass

    def esconder_janela(self):
        self.root.withdraw()

    def mostrar_janela(self):
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)

    def toggle_autostart(self):
        configurar_autostart(self.var_autostart.get())

    def gerar_resumo(self):
        if not os.path.exists(ARQUIVO_CSV):
            messagebox.showinfo("Resumo", "Nenhum dado registrado ainda.")
            return
        
        quedas, lentidoes, trocas_claro = 0, 0, 0
        try:
            with open(ARQUIVO_CSV, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    evento = row.get("Evento", "").lower()
                    prov = row.get("Provedor", "").upper()
                    
                    if "queda" in evento or "desconectado" in evento: quedas += 1
                    if "lenta" in evento or "instabilidade" in evento: lentidoes += 1
                    if "troca" in evento and "CLARO" in prov: trocas_claro += 1
            
            relatorio = (
                "📊 RELATÓRIO GERENCIAL DE REDE\n"
                "--------------------------------------------------\n"
                f"🚫 Quedas Totais de Internet: {quedas}\n"
                f"⚠️ Alertas de Lentidão / Instabilidade: {lentidoes}\n"
                f"🔄 Ativações do Provedor Claro (Backup): {trocas_claro}\n"
                "--------------------------------------------------\n"
                "Use os botões 'TXT' ou 'Excel' para ver horários exatos."
            )
            messagebox.showinfo("Resumo de Ocorrências", relatorio)
        except Exception:
            messagebox.showerror("Erro", "Não foi possível ler o histórico.")

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

    def obter_dados_conexao(self):
        """
        Consulta direta ao speedtest-config.php pegando tanto o ISP 
        quanto o IP público exato retornado na tag <client>.
        """
        headers = {'User-Agent': 'Mozilla/5.0'}
        isp_bruto = ""
        ip_publico = "--"

        try:
            r = requests.get("https://www.speedtest.net/speedtest-config.php", headers=headers, timeout=5)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                cliente = root.find('client')
                if cliente is not None:
                    isp_bruto = cliente.attrib.get('isp', '')
                    ip_publico = cliente.attrib.get('ip', '--')
        except Exception:
            pass

        # Se falhou ou veio vazio, usa fallback com ASN detalhado
        if not isp_bruto or isp_bruto == "Desconhecido":
            try:
                r_api = requests.get("http://ip-api.com/json/?fields=status,message,isp,org,as,query", timeout=5)
                dados = r_api.json()
                if dados.get("status") == "success":
                    isp_bruto = f"{dados.get('isp', '')} {dados.get('org', '')} {dados.get('as', '')}"
                    ip_publico = dados.get('query', '--')
            except Exception:
                isp_bruto = "Sem Conexão"
                ip_publico = "--"

        provedor = identificar_provedor_real(isp_bruto)
        return provedor, ip_publico

    def monitorar_loop(self):
        time.sleep(2)
        
        while True:
            provedor, ip_pub = self.obter_dados_conexao()
            latencia = checar_latencia_ip("8.8.8.8", 53)
            
            if latencia == 9999 or provedor == "Sem Conexão":
                novo_estado = "CAIDA"
                provedor = "Sem Conexão"
            elif latencia > 150:
                novo_estado = "LENTA"
            else:
                novo_estado = "NORMAL"

            cor_icone = self.COR_ALERTA if novo_estado == "CAIDA" else (self.COR_ATENCAO if novo_estado == "LENTA" else self.COR_SUCESSO)
            icone_txt = "🔴" if novo_estado == "CAIDA" else ("🟡" if novo_estado == "LENTA" else "🟢")
            txt_estado = "Desconectado" if novo_estado == "CAIDA" else ("Instável / Lenta" if novo_estado == "LENTA" else "Conexão Estável")

            self.root.after(0, lambda i=icone_txt, t=txt_estado, c=cor_icone: (self.lbl_icone.config(text=i, fg=c), self.lbl_status_geral.config(text=t)))
            self.root.after(0, lambda p=provedor: self.lbl_provedor.config(text=f"Provedor: {p}"))
            self.root.after(0, lambda ip=ip_pub: self.lbl_ip.config(text=f"IP Público: {ip}"))
            self.root.after(0, lambda l=latencia: self.lbl_latencia.config(text=f"Latência: {'--' if l==9999 else l} ms"))

            # Lógica de Notificações
            if self.primeira_execucao:
                self.estado_atual = novo_estado
                self.provedor_atual = provedor
                self.ip_atual = ip_pub
                self.primeira_execucao = False
                if provedor != "Sem Conexão":
                    self.enviar_notificacao("Monitor Ativo", f"Conectado via {provedor} ({ip_pub}).")
                    registrar_log("Monitoramento Iniciado", provedor, ip_pub)
            else:
                if novo_estado == "CAIDA" and self.estado_atual != "CAIDA":
                    self.enviar_notificacao("Falha Crítica!", "A conexão com a internet caiu.")
                    registrar_log("Queda Total (Desconectado)", "Sem Conexão", "--")
                
                elif novo_estado != "CAIDA" and self.estado_atual == "CAIDA":
                    self.enviar_notificacao("Internet Restaurada", f"Reconectado através da {provedor}.")
                    registrar_log("Conexão Restaurada", provedor, ip_pub)
                
                # Troca real: mudou o provedor de verdade (ou o IP mudou radicalmente de faixa)
                elif novo_estado != "CAIDA" and self.estado_atual != "CAIDA" and (provedor != self.provedor_atual and provedor != "Desconhecido"):
                    self.enviar_notificacao("Mudança de Rota", f"O provedor mudou de {self.provedor_atual} para {provedor}.")
                    registrar_log(f"Troca de Provedor Detectada (Era {self.provedor_atual})", provedor, ip_pub)
                
                if novo_estado == "LENTA" and self.estado_atual == "NORMAL":
                    self.enviar_notificacao("Instabilidade", f"Rede lenta. Latência de {latencia}ms.")
                    registrar_log(f"Lentidão / Instabilidade ({latencia}ms)", provedor, ip_pub)
                
                elif novo_estado == "NORMAL" and self.estado_atual == "LENTA":
                    self.enviar_notificacao("Rede Normalizada", "A latência da rede voltou ao normal.")
                    registrar_log("Estabilidade Normalizada", provedor, ip_pub)

            self.estado_atual = novo_estado
            self.provedor_atual = provedor
            self.ip_atual = ip_pub
            
            time.sleep(30)

def criar_icone():
    imagem = Image.new('RGB', (64, 64), color=(30, 30, 30))
    desenho = ImageDraw.Draw(imagem)
    desenho.ellipse((16, 16, 48, 48), fill=(0, 120, 255))
    return imagem

def iniciar_bandeja(app):
    def on_abrir(icon, item): app.mostrar_janela()
    def on_sair(icon, item):
        registrar_log("Monitor Encerrado pelo Usuário", app.provedor_atual, app.ip_atual)
        icon.stop()
        app.root.quit()
        sys.exit()

    menu = Menu(MenuItem("Abrir Painel", on_abrir, default=True), MenuItem("Sair", on_sair))
    icone = Icon("MonitorRede", criar_icone(), menu=menu)
    app.tray_icon = icone
    icone.run()

if __name__ == '__main__':
    app = MonitorApp()
    app.esconder_janela()
    threading.Thread(target=iniciar_bandeja, args=(app,), daemon=True).start()
    app.root.mainloop()
