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

# --- CONTROLE DE FUSO HORÁRIO ---
from datetime import datetime, timedelta, timezone

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

# --- FUNÇÃO MOTORA: GERA O PROTOCOLO ATUALIZADO ---
def anexar_pagina_assinatura(caminho_pdf_original, hash_original, nome_assinante, email_assinante, cpf_assinante, data_assinatura, setor_emissor, banco_completo, link_minuta_atual):
    caminho_protocolo_temp = caminho_pdf_original.replace(".pdf", "_protocolo_temp.pdf")
    
    try:
        nome_exibicao_doc = caminho_pdf_original.split(os.sep)[-1].split("_", 1)[-1]

        # CORREÇÃO CRÍTICA: Filtra rigorosamente apenas quem pertence a ESTE arquivo/lote específico
        co_assinantes = [reg for reg in banco_completo if str(reg.get("link_minuta")) == str(link_minuta_atual)]
        
        # Define a data de disponibilização baseada no lote atual
        data_disponibilizacao = co_assinantes[0].get("data_criacao", "-") if co_assinantes else "-"

        # Determina o STATUS Geral do Documento avaliando o lote específico
        algum_pendente = False
        for co in co_assinantes:
            # Desconsidera o assinante atual da checagem de pendência, pois ele está assinando agora
            if str(co.get("token")) == str(st.query_params.get("token")):
                continue
            if co.get("status") != "Assinado":
                algum_pendente = True
                break

        if algum_pendente:
            status_geral_html = "<font color='#C53030'><b>Pendente de assinaturas</b></font>"
        else:
            status_geral_html = "<font color='#2F855A'><b>Concluído e Validado</b></font>"

        doc = SimpleDocTemplate(caminho_protocolo_temp, pagesize=letter, leftMargin=45, rightMargin=45, topMargin=45, bottomMargin=45)
        story = []
        
        styles = getSampleStyleSheet()
        
        style_titulo = ParagraphStyle(
            'TituloProtocolo',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=16,
            textColor=colors.HexColor("#1A365D"),
            spaceAfter=12,
            alignment=1
        )
        
        style_secao = ParagraphStyle(
            'SubSecao',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=11,
            textColor=colors.HexColor("#2C5282"),
            spaceBefore=14,
            spaceAfter=6
        )
        
        style_texto = ParagraphStyle(
            'TextoComum',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#2D3748")
        )

        style_hash = ParagraphStyle(
            'TextoHash',
            parent=styles['Normal'],
            fontName='Courier',
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#4A5568")
        )
        
        # --- CORPO DO PDF ---
        story.append(Paragraph("PROTOCOLO DE ASSINATURA ELETRÔNICA", style_titulo))
        
        texto_intro = "Este documento foi processado eletronicamente. A autenticidade e a integridade do arquivo podem ser conferidas por meio do identificador de segurança posicionado no rodapé desta página."
        story.append(Paragraph(texto_intro, style_texto))
        story.append(Spacer(1, 4))
        
        # --- TABELA 1: INFORMAÇÕES DE EMISSÃO ---
        story.append(Paragraph("Informações de Emissão", style_secao))
        
        dados_doc = [
            [Paragraph(f"<b>Documento:</b> {nome_exibicao_doc}", style_texto), 
             Paragraph(f"<b>Disponibilizado em:</b> {data_disponibilizacao}", style_texto)],
            [Paragraph(f"<b>Setor Responsável:</b> {setor_emissor} / Prefeitura Municipal de Lençóis Paulista", style_texto),
             Paragraph(f"<b>STATUS:</b> {status_geral_html}", style_texto)]
        ]
        
        t_doc = Table(dados_doc, colWidths=[310, 210])
        t_doc.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F7FAFC")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ]))
        story.append(t_doc)
        
        # --- TABELA 2: DADOS DA ASSINATURA ATUAL ---
        story.append(Paragraph("Assinatura Processada Neste Momento", style_secao))
        
        texto_detalhes = f"""
        <b>Assinante Atual:</b> {nome_assinante}<br/>
        <b>E-mail:</b> {email_assinante}<br/>
        <b>Documento (CPF):</b> {cpf_assinante}<br/>
        <b>Data / Hora da Ação (Brasília):</b> {data_assinatura}
        """
        
        t_ass = Table([[Paragraph(texto_detalhes, style_texto)]], colWidths=[520])
        t_ass.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EDF2F7")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
            ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ]))
        story.append(t_ass)
        
        # --- TABELA 3: FLUXO E STATUS DOS INTEGRANTES DO LOTE ---
        story.append(Paragraph("Fluxo de Assinaturas do Documento", style_secao))
        
        dados_fluxo = [[Paragraph("<b>Nome do Integrante</b>", style_texto), 
                        Paragraph("<b>E-mail</b>", style_texto), 
                        Paragraph("<b>Data da Assinatura / Status</b>", style_texto)]]
        
        for co in co_assinantes:
            if str(co.get("token")) == str(st.query_params.get("token")):
                status_txt = f"<font color='#2F855A'><b>{data_assinatura}</b></font>"
            elif co.get("status") == "Assinado":
                status_txt = f"<font color='#2F855A'><b>{co.get('data')}</b></font>"
            else:
                status_txt = "<font color='#C53030'><b>Pendente</b></font>"
                
            dados_fluxo.append([
                Paragraph(str(co.get("nome")), style_texto),
                Paragraph(str(co.get("email")), style_texto),
                Paragraph(status_txt, style_texto)
            ])
            
        t_fluxo = Table(dados_fluxo, colWidths=[180, 180, 160])
        t_fluxo.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(t_fluxo)
        story.append(Spacer(1, 20))
        
        # --- TABELA 4: RODAPÉ COM IDENTIFICADOR HASH ---
        story.append(Paragraph("<b>Identificador de Validação Criptográfica (Hash SHA-256):</b>", style_texto))
        story.append(Spacer(1, 2))
        t_hash = Table([[Paragraph(str(hash_original), style_hash)]], colWidths=[520])
        t_hash.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F7FAFC")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(t_hash)
        
        doc.build(story)
        
        # UNIÃO DOS ARQUIVOS PDF
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
        if os.path.exists(caminho_protocolo_temp):
            os.remove(caminho_protocolo_temp)
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
def enviar_email_individual(meu_email, minha_senha, destino, nome, link, orgao_setor, nome_documento):
    try:
        msg = MIMEMultipart()
        msg['From'] = meu_email
        msg['To'] = destino
        msg['Subject'] = f"Assinatura Digital Pendente - {nome_documento}"
        
        corpo = f"Olá, {nome}.\n\nVocê foi incluído para assinar um documento da {orgao_setor}, chamado {nome_documento}.\n\nAcesse pelo link seguro abaixo para ler a minuta e assinar:\n{link}\n\nPara validar a assinatura, basta digitar seu nome completo e CPF. Não é necessário realizar login."
        
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        servidor = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        servidor.login(meu_email, minha_senha)
        servidor.sendmail(meu_email, destino, msg.as_string())
        servidor.quit()
        return True
    except:
        return False

# --- CONTROLE DE ESTADO E LEITURA DE PARÂMETROS ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

token_acesso = st.query_params.get("token", None)

# --- BANCO DE DADOS EM TEMPO REAL ---
lista_banco = ler_dados_planilha()

# --- MENU LATERAL DE ACESSO RESTRITO ---
with st.sidebar:
    st.sidebar.subheader("Controle")
    modo_admin = st.sidebar.checkbox("Ativar Modo Criador", value=st.session_state.autenticado)
    
    if modo_admin:
        senha = st.sidebar.text_input("Senha", type="password")
        if st.sidebar.button("🔓 Entrar"):
            if senha == "ChaveMestra123":
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.sidebar.error("Senha incorreta")
    else:
        st.session_state.autenticado = False

if token_acesso:
    st.session_state.autenticado = False

# --- CRIAÇÃO ESTÁVEL DAS ABAS ---
if st.session_state.autenticado:
    aba1, aba2, aba3, aba4 = st.tabs(["Criador", "Assinante", "Histórico", "📂 Arquivos Concluídos"])
else:
    abas_usuario = st.tabs(["Assinante"])
    aba2 = abas_usuario[0]

# --- CONTEÚDO: CRIADOR ---
if st.session_state.autenticado:
    with aba1:
        c1, c2 = st.columns(2)
        with c1:
            m_email = st.text_input("Gmail Envio", value=GMAIL_PADRAO)
            m_senha = st.text_input("Senha App", type="password")
            m_link = st.text_input("Link App", value=LINK_SISTEMA_PADRAO)
            
            m_orgao = st.text_input("Nome do Órgão / Setor responsável (Ex: Secretaria de Obras)")
            m_nome_doc = st.text_input("Nome de Identificação do Arquivo (Ex: Contrato_Locacao_01)")
            
            m_arq = st.file_uploader("Contrato PDF (Minuta)", type=["pdf"])
            m_lote = st.text_area("Lista (Nome; Email)")
            
            if st.button("🚀 Enviar Lote", type="primary"):
                if m_arq is not None and m_lote.strip() and m_senha and m_nome_doc.strip() and m_orgao.strip():
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
                        
                        fuso_br = timezone(timedelta(hours=-3))
                        data_criacao_lote = datetime.now(fuso_br).strftime("%d/%m/%Y")
                        
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
                                    "link_minuta": nome_salvo_local,
                                    "setor": m_orgao.strip(),
                                    "data_criacao": data_criacao_lote
                                })
                                
                                link_personalizado = f"{base_url}?token={token}"
                                enviar_email_individual(
                                    meu_email=m_email, 
                                    minha_senha=m_senha, 
                                    destino=email_limpo, 
                                    nome=nome_limpo, 
                                    link=link_personalizado,
                                    orgao_setor=m_orgao.strip(),
                                    nome_documento=m_nome_doc.strip()
                                )
                            progresso.progress((idx + 1) / total)
                        
                        lista_updated = lista_banco + novos_assinantes if lista_banco else novos_assinantes
                        salvar_dados_planilha(lista_updated)
                        st.success("Lote enviado e gravado com sucesso!")
                        st.rerun()
                else:
                    st.error("Erro: Preencha TODOS os campos (incluindo o Órgão/Setor, Nome do arquivo, Minuta, Lista e Senha).")
        with c2:
            st.subheader("📋 Assinaturas Pendentes")
            if lista_banco:
                df_completo = pd.DataFrame(lista_banco)
                
                if "status" in df_completo.columns and "link_minuta" in df_completo.columns:
                    df_pendente = df_completo[df_completo["status"] == "Pendente"].copy()
                    
                    if not df_pendente.empty:
                        df_pendente["Arquivo"] = df_pendente["link_minuta"].apply(lambda x: str(x).split("_", 1)[-1] if "_" in str(x) else x)
                        colunas_ordenadas = ["Arquivo", "setor", "nome", "email", "status"]
                        colunas_existentes = [c for c in colunas_ordenadas if c in df_pendente.columns]
                        
                        st.dataframe(
                            df_pendente[colunas_existentes].rename(columns={"setor": "Órgão/Setor", "nome": "Nome", "email": "E-mail", "status": "Status"}),
                            width="stretch",
                            hide_index=True
                        )
                    else:
                        st.success("🎉 Excelente! Não há nenhuma assinatura pendente no momento.")
                else:
                    st.dataframe(df_completo, width="stretch")
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
                        fuso_brasilia = timezone(timedelta(hours=-3))
                        data_formatada = datetime.now(fuso_brasilia).strftime("%d/%m/%Y %H:%M:%S")
                        
                        sucesso_pdf = anexar_pagina_assinatura(
                            caminho_pdf_original=caminho_completo_pdf,
                            hash_original=a.get("hash_doc", "Não informado"),
                            nome_assinante=c_nome,
                            email_assinante=a.get("email", ""),
                            cpf_assinante=c_cpf,
                            data_assinatura=data_formatada,
                            setor_emissor=a.get("setor", "Não Informado"),
                            banco_completo=lista_banco,
                            link_minuta_atual=nome_do_pdf
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

# --- CONTEÚDO: ABA 4 ARQUIVOS CONCLUÍDOS ---
if st.session_state.autenticado:
    with aba4:
        st.subheader("📂 Download de Documentos Completamente Assinados")
        st.caption("Esta área é restrita e exibe apenas os arquivos que já receberam a folha de protocolo.")
        
        if lista_banco:
            assinados = [reg for reg in lista_banco if reg.get("status") == "Assinado"]
            
            if assinados:
                arquivos_processados = set()
                
                for doc_assinado in assinados:
                    nome_arquivo_sistema = doc_assinado.get("link_minuta")
                    
                    if nome_arquivo_sistema and nome_arquivo_sistema not in arquivos_processados:
                        arquivos_processados.add(nome_arquivo_sistema)
                        caminho_pdf_final = os.path.join(PASTA_LOCAL_MINUTAS, nome_arquivo_sistema)
                        nome_exibicao_limpo = nome_arquivo_sistema.split("_", 1)[-1]
                        
                        col_nome, col_btn, col_del = st.columns([3, 1, 1])
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
                                st.error("Arquivo não localizado") # PONTO REMOVIDO DAQUI CORETAMENTE
                        
                        with col_del:
                            if st.button("❌ Deletar do Sistema", key=f"del_{nome_arquivo_sistema}", type="secondary"):
                                if os.path.exists(caminho_pdf_final):
                                    os.remove(caminho_pdf_final)
                                
                                lista_filtrada = [reg for reg in lista_banco if reg.get("link_minuta") != nome_arquivo_sistema]
                                salvar_dados_planilha(lista_filtrada)
                                
                                st.success(f"Arquivo {nome_exibicao_limpo} excluído!")
                                st.rerun()
                                
                        st.divider()
            else:
                st.info("Nenhum documento assinado foi registrado até o momento.")
        else:
            st.info("Aguardando sincronização de dados.")
