import hashlib
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import streamlit as st
import pandas as pd
from gspread_dataframe import set_with_dataframe
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(
    page_title="Plataforma de Assinaturas",
    page_icon="🖋️",
    layout="wide"
)

# --- CONFIGURAÇÕES FIXAS (URL ATUALIZADA PARA ENGENHARIAPMLP) ---
GMAIL_PADRAO = "soiassinadorpmlp@gmail.com"
LINK_SISTEMA_PADRAO = "https://engenhariapmlp.streamlit.app"
SPREADSHEET_ID = "13Vyiy-XBzR969JPTMJlWK3gpKcLRi9ftVRcO3kinoWE"

# --- CONEXÃO DIRETA VIA ARQUIVO FÍSICO JSON ---
def obter_cliente_sheets():
    escopos = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file('credenciais.json', scopes=escopos)
    return gspread.authorize(creds)

def ler_dados_planilha():
    try:
        gc = obter_cliente_sheets()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.get_worksheet(0)
        return worksheet.get_all_records()
    except Exception as e:
        st.error(f"Erro ao acessar a planilha de assinaturas: {e}")
        return []

def salvar_dados_planilha(lista_assinantes):
    try:
        gc = obter_cliente_sheets()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.get_worksheet(0)
        worksheet.clear()
        df = pd.DataFrame(lista_assinantes)
        set_with_dataframe(worksheet, df)
    except Exception as e:
        st.error(f"Erro ao salvar dados no sistema: {e}")

# --- CONTROLE DE ESTADO (SESSION STATE) ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

token_acesso = st.query_params.get("token", None)

# --- MOTOR DE DISPARO DE E-MAIL ---
def enviar_email_individual(meu_email, minha_senha, destino, nome, link):
    try:
        msg = MIMEMultipart()
        msg['From'] = meu_email
        msg['To'] = destino
        msg['Subject'] = "Assinatura Digital Pendente"
        
        corpo = f"Olá, {nome}.\n\nVocê foi incluído para assinar um documento oficial.\n\nAcesse pelo link seguro abaixo:\n{link}\n\nDigite seu NOME e CPF para validar. Não precisa de login."
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        servidor = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        servidor.login(meu_email, minha_senha)
        servidor.sendmail(meu_email, destino, msg.as_string())
        servidor.quit()
        return True
    except:
        return False

# --- MENU LATERAL DE ACESSO RESTRITO ---
with st.sidebar:
    st.subheader("Controle")
    modo_admin = st.checkbox("Ativar Modo Criador", value=st.session_state.autenticado)
    
    if modo_admin:
        senha = st.text_input("Senha", type="password")
        if st.button("🔓 Entrar"):
            if senha == "ChaveMestra123":
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Senha incorreta")
    else:
        st.session_state.autenticado = False

if token_acesso:
    st.session_state.autenticado = False

# --- DEFINE VISIBILIDADE DAS ABAS ---
if st.session_state.autenticado:
    aba1, aba2, aba3 = st.tabs(["Criador", "Assinante", "Histórico"])
else:
    aba2, = st.tabs(["Assinante"])

# --- LER BANCO DE DADOS EM TEMPO REAL ---
lista_banco = ler_dados_planilha()

# --- CONTEÚDO: CRIADOR ---
if st.session_state.autenticado:
    with aba1:
        c1, c2 = st.columns(2)
        with c1:
            m_email = st.text_input("Gmail Envio", value=GMAIL_PADRAO)
            m_senha = st.text_input("Senha App", type="password")
            m_link = st.text_input("Link App", value=LINK_SISTEMA_PADRAO)
            m_arq = st.file_uploader("Contrato PDF", type=["pdf"])
            m_lote = st.text_area("Lista (Nome; Email)")
            
            if st.button("🚀 Enviar Lote", type="primary"):
                if m_arq is not None and m_lote.strip() and m_senha:
                    pdf_conteudo = m_arq.getvalue()
                    hasher = hashlib.sha256()
                    hasher.update(pdf_conteudo)
                    hash_seguranca = hasher.hexdigest()
                    
                    linhas = m_lote.strip().split("\n")
                    base_url = m_link.split("?")[0]
                    novos_assinantes = []
                    
                    progresso = st.progress(0)
                    total = len(linhas)
                    
                    for idx, linha in enumerate(linhas):
                        if ";" in linha:
                            partes = linha.split(";")
                            nome_limpo = partes[0].strip()
                            email_limpo = partes[1].strip()
                            token = secrets.token_hex(4)
                            
                            novos_assinantes.append({
                                "token": token,
                                "nome": nome_limpo,
                                "email": email_limpo,
                                "cpf": "",
                                "status": "Pendente",
                                "data": "-",
                                "hash_doc": hash_seguranca
                            })
                            
                            link_personalizado = f"{base_url}?token={token}"
                            enviar_email_individual(m_email, m_senha, email_limpo, nome_limpo, link_personalizado)
                        progresso.progress((idx + 1) / total)
                        
                    salvar_dados_planilha(novos_assinantes)
                    st.success("Lote enviado e salvo com sucesso!")
                    st.rerun()
                else:
                    st.error("Erro: Preencha o arquivo, a lista e a senha do Gmail (Senha de App).")
        with c2:
            st.subheader("Planilha Ativa")
            if lista_banco:
                st.dataframe(pd.DataFrame(lista_banco), width="stretch")
            else:
                st.info("Nenhum dado na planilha ou aguardando sincronização.")

# --- CONTEÚDO: ASSINANTE ---
with aba2:
    st.title("🖋️ Assinatura Eletrônica de Documentos")
    
    assinante_atual = None
    if token_acesso and lista_banco:
        for a in lista_banco:
            if str(a.get("token")) == str(token_acesso):
                assinante_atual = a
                break

    st.subheader("1. Identificação do Assinante")
    if assinante_atual:
        st.success(f"Documento localizado para: {assinante_atual['nome']}")
    else:
        if token_acesso:
            st.error("Token inválido ou expirado.")
        else:
            st.warning("Aguardando link de acesso exclusivo enviado por e-mail.")

    c_nome = st.text_input("Nome Completo", value=assinante_atual["nome"] if assinante_atual else "")
    c_cpf = st.text_input("CPF")
    
    if st.button("✍️ Confirmar Assinatura", type="primary"):
        if not lista_banco:
            st.error("Erro: Banco de dados vazio.")
        elif not c_nome or not c_cpf:
            st.error("Erro: Preencha todos os campos.")
        else:
            encontrado = False
            for a in lista_banco:
                valido = False
                if token_acesso:
                    valido = (str(a.get("token")) == str(token_acesso) and a.get("status") == "Pendente")
                else:
                    valido = (str(a.get("nome")).lower() == c_nome.lower() and a.get("status") == "Pendente")
                    
                if valido:
                    a["status"] = "Assinado"
                    a["cpf"] = c_cpf
                    a["data"] = "25/06/2026"
                    encontrado = True
                    break
            
            if not encontrado:
                st.error("Erro: Assinatura inválida ou lote já concluído.")
            else:
                salvar_dados_planilha(lista_banco)
                st.success("Assinatura confirmada com sucesso!")
                st.balloons()
                st.rerun()

# --- CONTEÚDO: HISTÓRICO ---
if st.session_state.autenticado:
    with aba3:
        st.subheader("Histórico de Assinaturas (Realtime)")
        if lista_banco:
            st.dataframe(pd.DataFrame(lista_banco), width="stretch")
