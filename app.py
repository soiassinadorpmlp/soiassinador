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
        
        # 1. Configuração do documento ReportLab
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
        
        # 2. Mesclar folhas
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

# --- DEFINE VISIBILIDADE DAS ABAS (ADICIONADA ABA DE ARQUIVOS ASSINADOS) ---
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
            
            # NOVO CAMPO: Nome final personalizado para o arquivo
            m_nome_doc = st.text_input("Nome de Identificação do Arquivo (Ex: Contrato_Locacao_01)")
            
            m_arq = st.file_uploader("Contrato PDF (Minuta)", type=["pdf"])
            m_lote = st.text_area("Lista (Nome; Email)")
            
            if st.button("🚀 Enviar Lote", type="primary"):
                if m_arq is not None and m_lote.strip() and m_senha and m_nome_doc.strip():
                    pdf_conteudo = m_arq.getvalue()
                    
                    st.info("Processando e salvando a minuta com segurança...")
                    
                    # Trata o nome digitado para garantir que termine com .pdf sem espaços perigosos
                    nome_final_pdf = m_nome_doc.strip().replace(" ", "_")
                    if not nome_final_pdf.lower().endswith(".pdf"):
                        nome_final_pdf += ".pdf"
                    
                    token_do_lote = secrets.token_hex(4)
                    # O arquivo agora é guardado com o nome exato inserido no input
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
        
        nome_do_pdf = assinante_atual.get("link_minuta")
        caminho_completo_pdf = os.path.join(PASTA_LOCAL_MINUTAS, nome_do_pdf) if nome_do_pdf else ""
        
        # AJUSTE DE SEGURANÇA: O assinante só vê o botão de download se ainda NÃO tiver assinado
        if assinante_atual["status"] == "Pendente":
            if nome_do_pdf and os.path.exists(caminho_completo_pdf):
                st.markdown(f'### 📄 2. Leitura Obrigatória')
                
                with open(caminho_completo_pdf, "rb") as f_pdf:
                    bytes_pdf = f_pdf.read()
                
                st.download_button(
                    label="👉 Clique para baixar e ler a Minuta do Contrato (PDF)",
                    data=bytes_pdf,
                    file_name=nome_do_pdf.split("_", 1)[-1],
                    mime="application/pdf",
                    type="primary"
                )
                st.caption("Verifique todas as cláusulas do arquivo oficial baixado antes de prosseguir para a assinatura abaixo.")
            else:
                st.warning("O arquivo PDF desta minuta não foi localizado no servidor.")
    else:
        if token_acesso:
            st.error("Token inválido ou expirado.")
        else:
            st.warning("Aguardando link de acesso exclusivo enviado por e-mail.")

    if assinante_atual and assinante_atual["status"] == "Pendente":
        st.markdown("### 📝 3. Validação Jurídica")
        c_nome = st.text_input("Confirmar Nome Completo", value=assinante_atual["nome"] if assinante_atual else "")
        c_cpf = st.text_input("Digitar CPF para assinatura")
        
        if st.button("✍️ Confirmar Assinatura", type="primary"):
            if not lista_banco:
                st.error("Erro: Banco de dados vazio.")
            elif not c_nome or not c_cpf:
                st.error("Erro: Preencha todos os campos.")
            else:
                encontrado = False
                for a in lista_banco:
                    valido = str(a.get("token")) == str(token_acesso) and a.get("status") == "Pendente"
                        
                    if valido:
                        from datetime import datetime
                        data_formatada = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        
                        sucesso_pdf = anexar_pagina_assinatura(
                            caminho_pdf_original=caminho_completo_pdf,
                            hash_original=a.get("hash_doc", "Não informado"),
                            nome_assinante=c_nome,
                            email_assinante=a.get("email", ""),
                            cpf_assinante=c_cpf,
                            data_assinatura=data_formatada
                        )
                        
                        if sucesso_pdf:
                            a["status"] = "Assinado"
                            a["cpf"] = c_cpf
                            a["data"] = data_formatada
                            encontrado = True
                        break
                
                if not encontrado:
                    st.error("Erro: Falha ao processar assinatura ou o lote já foi assinado.")
                else:
                    salvar_dados_planilha(lista_banco)
                    st.success("Sua assinatura foi validada e registrada com sucesso!")
                    st.balloons()
                    st.rerun()
    elif assinante_atual and assinante_atual["status"] == "Assinado":
        st.info("Este documento já foi devidamente assinado e validado eletronicamente. Obrigado!")

# --- CONTEÚDO: HISTÓRICO ---
if st.session_state.autenticado:
    with aba3:
        st.subheader("Histórico de Assinaturas (Realtime)")
        if lista_banco:
            st.dataframe(pd.DataFrame(lista_banco), width="stretch")

# --- CONTEÚDO: NOVA ABA 4 EXCLUSIVA DO CRIADOR (DOWNLOADS DOS CONCLUÍDOS) ---
if st.session_state.autenticado:
    with aba4:
        st.subheader("📂 Download de Documentos Completamente Assinados")
        st.caption("Esta área é restrita e exibe apenas os arquivos que já receberam a folha de protocolo.")
        
        if lista_banco:
            # Filtra apenas os registros com status "Assinado"
            assinados = [reg for reg in lista_banco if reg.get("status") == "Assinado"]
            
            if assinados:
                # Agrupa por arquivo único para não repetir botões se houver múltiplos assinantes no mesmo lote
                arquivos_processados = set()
                
                for doc_assinado in assinados:
                    nome_arquivo_sistema = doc_assinado.get("link_minuta")
                    
                    if nome_arquivo_sistema and nome_arquivo_sistema not in arquivos_processados:
                        arquivos_processados.add(nome_arquivo_sistema)
                        caminho_pdf_final = os.path.join(PASTA_LOCAL_MINUTAS, nome_arquivo_sistema)
                        
                        # Nome legível sem o token inicial para exibição na tela
                        nome_exibicao_limpo = nome_arquivo_sistema.split("_", 1)[-1]
                        
                        col_nome, col_btn = st.columns([3, 1])
                        with col_nome:
                            st.markdown(f"📄 **{nome_exibicao_limpo}**")
                            st.caption(f"Assinado por: {doc_assinado.get('nome')} ({doc_assinado.get('data')})")
                        
                        with col_btn:
                            if os.path.exists(caminho_pdf_final):
                                with open(caminho_pdf_final, "rb") as f_down:
                                    bytes_down = f_down.read()
                                st.download_button(
                                    label="⬇️ Baixar PDF Final",
                                    data=bytes_down,
                                    file_name=nome_exibicao_limpo,
                                    mime="application/pdf",
                                    key=f"down_{nome_arquivo_sistema}"
                                )
                            else:
                                st.error("Arquivo não localizado")
                        st.divider()
            else:
                st.info("Nenhum documento assinado foi registrado até o momento.")
        else:
            st.info("Aguardando sincronização de dados.")
