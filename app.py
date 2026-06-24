import hashlib
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter

# --- CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(page_title="Plataforma de Assinaturas", page_icon="🖋️", layout="wide")

# --- CONFIGURAÇÕES FIXAS DA PLATAFORMA ---
GMAIL_PADRAO = "soiassinadorpmlp@gmail.com"
LINK_SISTEMA_PADRAO = "https://soiassinador.streamlit.app"

# --- MEMÓRIA DO SISTEMA DE SESSÃO ---
if "banco_dados" not in st.session_state:
    st.session_state.banco_dados = {
        "caminho_original": None,
        "conteudo_original": None,
        "hash_seguranca": None,
        "assinantes": []
    }

if "modo_administrador" not in st.session_state:
    st.session_state.modo_administrador = False

# --- LEITURA DO TOKEN EXCLUSIVO DA URL (NÃO EXIGE LOGIN) ---
url_params = st.query_params
token_acesso = url_params.get("token", None)

def obter_tabela_historico():
    if not st.session_state.banco_dados["assinantes"]:
        return []
    dados_tabela = []
    for a in st.session_state.banco_dados["assinantes"]:
        dados_tabela.append({
            "Nome": a["nome"],
            "E-mail": a["email"],
            "Status": a["status"],
            "CPF Utilizado": a["cpf"],
            "Data/Hora": a["data"],
            "Token": a["token"]
        })
    return dados_tabela

# --- MOTOR DE DISPARO REAL ---
def enviar_email_individual(meu_email, minha_senha_app, email_destino, nome_assinante, link_personalizado):
    try:
        servidor_smtp = "smtp.gmail.com"
        porta = 465
        msg = MIMEMultipart()
        msg['From'] = meu_email
        msg['To'] = email_destino
        msg['Subject'] = "Assinatura Pendente - Plataforma Digital"
        
        corpo = f"""Olá, {nome_assinante}.

Você foi incluído como assinante de um documento oficial em nossa plataforma.

⚠️ INSTRUÇÕES IMPORTANTES PARA A ASSINATURA:
1. Confira a grafia do seu nome para a assinatura: {nome_assinante}
2. Acesse a plataforma pelo seu link exclusivo de acesso seguro:
{link_personalizado}

3. Leia atentamente a minuta do documento disponível na tela.
4. Digite obrigatoriamente o seu NOME COMPLETO (exatamente com a grafia acima) e o seu CPF para validar o documento.

Não é necessário criar conta ou fazer login para assinar.
"""
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        
        servidor = smtplib.SMTP_SSL(servidor_smtp, porta)
        servidor.login(meu_email, minha_senha_app)
        servidor.sendmail(meu_email, email_destino, msg.as_string())
        servidor.quit()
        return True
    except:
        return False

# --- PROCESSAR ENTRADA DE LOTE ---
def criador_processa_lote(arquivo_pdf, texto_assinantes, meu_email, minha_senha_app, link_sistema):
    if arquivo_pdf is None:
        return st.error("ERRO: Anexe um arquivo PDF.")
    if not texto_assinantes.strip():
        return st.error("ERRO: Insira pelo menos 1 assinante.")
    if not meu_email or not minha_senha_app:
        return st.error("ERRO: Configure suas credenciais de e-mail.")
    if not link_sistema.strip():
        return st.error("ERRO: Insira o link do seu sistema.")

    st.session_state.banco_dados["caminho_original"] = arquivo_pdf.name
    st.session_state.banco_dados["conteudo_original"] = arquivo_pdf.getvalue()
    st.session_state.banco_dados["assinantes"] = []
    
    hasher = hashlib.sha256()
    hasher.update(st.session_state.banco_dados["conteudo_original"])
    st.session_state.banco_dados["hash_seguranca"] = hasher.hexdigest()

    linhas = texto_assinantes.strip().split("\n")
    emails_enviados = 0
    linhas_ignoradas = 0
    
    base_url = link_sistema.split("?")[0]
    
    for linha in linhas:
        if ";" in linha:
            partes = linha.split(";")
            nome_limpo = partes[0].strip()
            email_limpo = partes[1].strip()
            token = secrets.token_hex(4)
            
            st.session_state.banco_dados["assinantes"].append({
                "nome": nome_limpo, "email": email_limpo, "token": token,
                "cpf": "", "status": "Pendente", "data": "-"
            })
            
            link_personalizado = f"{base_url}?token={token}"
            
            sucesso = enviar_email_individual(meu_email, minha_senha_app, email_limpo, nome_limpo, link_personalizado)
            if sucesso:
                emails_enviados += 1
        else:
            linhas_ignoradas += 1

    total_cadastrados = len(st.session_state.banco_dados["assinantes"])
    relatorio = f"""=== LOTE PROCESSADO ===
1. Hash SHA-256: {st.session_state.banco_dados['hash_seguranca']}
2. Disparos: {emails_enviados} e-mails enviados com sucesso.
3. Linhas ignoradas: {linhas_ignoradas}
4. Total na memória: {total_cadast
