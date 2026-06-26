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
import base64
import json
import os

# --- BIBLIOTECAS PARA MANIPULAÇÃO DE PDF ---
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(
    page_title="Plataforma de Assinaturas",
    page_icon="🖋️",
    layout="wide"
)

# --- CONFIGURAÇÕES FIXAS ---
GMAIL_PADRAO = "soiassinadorpmlp@gmail.com"
LINK_SISTEMA_PADRAO = "https://engenhariapmlp.streamlit.app"
SPREADSHEET_ID = "13Vyiy-XBzR969JPTMJlWK3gpKcLRi9ftVRcO3kinoWE"

PASTA_LOCAL_MINUTAS = "minutas"
if not os.path.exists(PASTA_LOCAL_MINUTAS):
    os.makedirs(PASTA_LOCAL_MINUTAS)

# --- CONEXÃO SEGURA VIA BASE64 ---
def obter_credenciais():
    escopos = ["https://www.googleapis.com/auth/spreadsheets"]
    b64_data = st.secrets["GOOGLE_CREDS_BASE64"]
    json_string = base64.b64decode(b64_data).decode('utf-8')
    creds_dict = json.loads(json_string)
    return Credentials.from_service_account_info(creds_dict, scopes=escopos)

def obter_cliente_sheets():
    try:
        creds = obter_credenciais()
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro crítico nas credenciais do Sheets: {e}")
        return None

# --- FUNÇÃO MOTORA: GERA A PÁGINA DE ASSINATURA E JUNTA AO PDF ORIGINAL ---
def anexar_pagina_assinatura(caminho_pdf_original, hash_original, nome_assinante, email_assinante, cpf_assinante, data_assinatura):
    try:
        caminho_protocolo_temp = caminho_pdf_original.replace(".pdf", "_protocolo_temp.pdf")
        
        doc = SimpleDocTemplate(caminho_protocolo_temp, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        story = []
        
        styles = getSampleStyleSheet()
        
        style_titulo = ParagraphStyle(
            'TituloProtocolo',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=22,
            textColor=colors.HexColor("#1A365D"),
            spaceAfter=12
        )
        
        style_label = ParagraphStyle(
            'LabelHash',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=11,
            textColor=colors.HexColor("#4A5568"),
            spaceAfter=2
        )
        
        style_hash = ParagraphStyle(
            'HashSHA',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=11,
            textColor=colors.HexColor("#718096"),
            spaceAfter=15
        )
        
        story.append(Paragraph("PROTOCOLO DE ASSINATURAS DIGITAIS", style_titulo))
        story.append(Paragraph("Identificador Único (Hash SHA-256) do Original:", style_label))
        story.append(Paragraph(str(hash_original), style_hash))
        
        t_linha = Table([[""]], colWidths=[540], rowHeights=[1])
        t_linha.setStyle(TableStyle([
            ('LINEBELOW', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E0")),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0)
        ]))
        story.append(t_linha)
        story.append(Spacer(1, 25))
        
        texto_bloco = f"""
        <b>Assinante: {nome_assinante}</b><br/><br/>
        <font color="#4A5568">E-mail:</font> {email_assinante}<br/><br/>
        <font color="#2F855A"><b>STATUS: ASSINADO | CPF: {cpf_assinante} | Data: {data_assinatura}</b></font>
        """
        
        style_bloco = ParagraphStyle(
            'BlocoAssinante',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=12,
            leading=14
        )
        
        p_bloco = Paragraph(texto_bloco, style_bloco)
        
        t_bloco = Table([[p_bloco]], colWidths=[540])
        t_bloco.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F7FAFC")),
            ('TOPPADDING', (0,0), (-1,-1), 14),
            ('BOTTOMPADDING', (0,0), (-1,-1), 14),
            ('LEFTPADDING', (0,0), (-1,-1), 14),
            ('RIGHTPADDING', (0,0), (-1,-1), 14),
        ]))
        story.append(t_bloco)
        
        doc.build(story)
        
        reader_original = PdfReader(caminho_pdf_original)
        reader_protocolo = PdfReader(caminho_protocolo_temp)
        writer = PdfWriter()
        
        for page in reader_original.pages:
            writer.add_page(page)
            
        writer.add_page(reader_protocolo.pages[0])
        
        with open(caminho_pdf_original, "wb") as f_saida:
            writer.write(f_saida)
            
        if os.path.exists(caminho_protocolo_temp):
            os.remove(caminho_protocolo_temp)
            
        return True
    except Exception as e:
        st.error(f"Erro técnico na junção do protocolo ao PDF: {e}")
        return False

# --- INTERAÇÃO COM PLANILHA ---
def ler_dados_planilha():
    try:
        gc = obter_cliente_sheets()
        if gc is None:
            return []
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.get_worksheet(0)
        return worksheet.get_all_records()
    except Exception as e:
        st.error(f"Erro ao acessar a planilha de assinaturas: {e}")
        return []

def salvar_dados_planilha(lista_assinantes):
    try:
        gc = obter_cliente_sheets()
        if gc is None:
            return
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.get_worksheet(0)
        worksheet.clear()
        df = pd.DataFrame(lista_assinantes)
        set_with_dataframe(worksheet, df)
    except Exception as e:
        st.error(f"Erro ao salvar dados no sistema: {e}")

# --- MOTOR DE DISPARO DE E-MAIL ---
def enviar_email_individual(meu_email, minha_senha, destino, nome, link):
    try:
        msg = MIMEMultipart()
        msg['From'] = meu_email
        msg['To'] = destino
        msg['Subject'] = "Assinatura Digital Pendente"
        
        corpo = f"Olá, {nome}.\n\nVocê foi incluído para assinar um documento oficial da engenharia.\n\nAcesse pelo link seguro abaixo para ler a minuta e assinar:\n{link}\n\nDigite seu NOME e CPF para validar. Não precisa de login."
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        servidor = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        servidor.login(meu_email, minha_senha)
        servidor.sendmail(meu_email, destino, msg.as_string())
        servidor.quit()
        return True
    except:
        return False

# --- CONTROLE DE ESTADO (SESSION STATE) ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

token_acesso = st.query_params.get("token", None)

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
    aba1, aba2, aba3, aba4 = st.tabs(["Criador", "Assinante", "Histórico", "📂 Arquivos Concluídos"])
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
            
            m_nome_doc = st.text_input("Nome de Identificação do Arquivo (Ex: Contrato_Locacao_01)")
            
            m_arq = st.file_uploader("Contrato PDF (Minuta)", type=["pdf"])
            m_lote = st.text_area("Lista (Nome; Email)")
            
            if st.button("🚀 Enviar Lote", type="primary"):
                if m_arq is not None and m_lote.strip() and m_senha and m_nome_doc.strip():
                    pdf_conteudo = m_arq.getvalue()
                    
                    st.info("Processando e salvando a minuta com segurança...")
                    
                    nome_final_pdf = m_nome_doc.strip().replace(" ", "_")
                    if not nome_final_pdf.lower().endswith(".pdf"):
                        nome_final_pdf += ".pdf"
                    
                    token_do_lote = secrets.token_hex(4)
                    nome_salvo_local = f"{token_do_lote}_{nome_final_pdf}"
                    
                    caminho_final = os.path.join(PASTA_LOCAL_MINUTAS, nome_salvo_local)
                    try:
                        with open(caminho_final, "wb") as f:
                            f.write(pdf_conteudo)
                        sucesso_salvamento = True
                    except:
                        sucesso_salvamento = False
                    
                    if not sucesso_salvamento:
                        st.error("Falha ao salvar o arquivo no servidor do sistema.")
                    else:
                        hasher = hashlib.sha256()
                        hasher.update(pdf_conteudo)
                        hash_seguranca = hasher.hexdigest()
                        
                        linhas = m_lote.strip().split("\n")
                        base_url = m_link.split("?")[0]
                        novos_assinantes = []
                        
                        progresso = st.progress(0)
                        total = len(linhas)
                        
                        for idx, inline in enumerate(linhas):
                            if ";" in inline:
                                partes = inline.split(";")
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
                                    "hash_doc": hash_seguranca,
                                    "link_minuta": nome_salvo_local
                                })
                                
                                link_personalizado = f"{base_url}?token={token}"
                                enviar_email_individual(m_email, m_senha, email_limpo, nome_limpo, link_personalizado)
                            progresso.progress((idx + 1) / total)
                        
                        lista_updated = lista_banco + novos_assinantes if lista_banco else novos_assinantes
                        salvar_dados_planilha(lista_updated)
                        st.success("Lote enviado e gravado com sucesso!")
                        st.rerun()
                else:
                    st.error("Erro: Preencha TODOS os campos, incluindo o nome do arquivo, minuta, lista e senha.")
        with c2:
            st.subheader("Planilha Ativa")
            if lista_banco:
                st.dataframe(pd.DataFrame(lista_banco), width="stretch")
            else:
                st.info("Nenhum dado na planilha ou aguardando sincronização.")

# --- CONTEÚDO: ASSINANTE ---
with
