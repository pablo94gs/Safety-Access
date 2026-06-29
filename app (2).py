import streamlit as st
import pandas as pd
import pdfplumber
import re
import base64
import os
import io
import json
import unicodedata
from datetime import datetime, date

st.set_page_config(
    page_title="Security Access - Quimpac Ecuador",
    page_icon="static/logo.png",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ─── LOGO BASE64 ──────────────────────────────────────────────────────────────
@st.cache_data
def get_logo_b64():
    try:
        with open("static/logo.png", "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""


LOGO_B64 = get_logo_b64()

# ─── IDs Google Sheets / Drive ────────────────────────────────────────────────
GS_CONTRATISTAS = "15mQCUavdet-Yt1XIe3uMEk8x2eCZu8TL"
GS_USUARIOS = "1NY0RalNq2a3oDha6EzAWdmsy_MabaLXv"
DRIVE_FOLDER_ID = "1aWHhxl8oSLcwBLqAS5I7S13DxKuww_fb"
UPLOADS_DIR = "uploads"
os.makedirs(UPLOADS_DIR, exist_ok=True)


# ─── GOOGLE DRIVE ─────────────────────────────────────────────────────────────
def _drive_service():
    """Construye el cliente de Drive desde la variable de entorno GOOGLE_SA_JSON."""
    raw = os.environ.get("GOOGLE_SA_JSON", "")
    if not raw:
        return None
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        info = json.loads(
            base64.b64decode(raw).decode() if not raw.strip().startswith("{") else raw
        )
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/drive"]
        )
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        st.warning(f"Google Drive: error al inicializar credenciales — {e}")
        return None


def _normalizar(nombre: str) -> str:
    """Normaliza el nombre de empresa: sin tildes, minúsculas, sin caracteres especiales."""
    nfkd = unicodedata.normalize("NFKD", nombre.strip())
    sin_tildes = "".join(c for c in nfkd if not unicodedata.combining(c))
    limpio = re.sub(r"[^a-z0-9]+", "_", sin_tildes.lower()).strip("_")
    return limpio


@st.cache_data(ttl=120)
def _listar_carpetas_drive(parent_id: str):
    """Devuelve dict {nombre_normalizado: folder_id} de subcarpetas."""
    svc = _drive_service()
    if not svc:
        return {}
    try:
        q = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        res = svc.files().list(q=q, fields="files(id,name)").execute()
        return {_normalizar(f["name"]): f["id"] for f in res.get("files", [])}
    except Exception:
        return {}


def _obtener_o_crear_carpeta(empresa: str) -> str | None:
    """Devuelve el ID de la carpeta de la empresa en Drive (la crea si no existe)."""
    svc = _drive_service()
    if not svc:
        return None
    norm = _normalizar(empresa)
    existentes = _listar_carpetas_drive(DRIVE_FOLDER_ID)
    if norm in existentes:
        return existentes[norm]
    try:
        meta = {
            "name": empresa.strip(),
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [DRIVE_FOLDER_ID],
        }
        folder = svc.files().create(body=meta, fields="id").execute()
        _listar_carpetas_drive.clear()
        return folder["id"]
    except Exception as e:
        st.warning(f"No se pudo crear carpeta en Drive: {e}")
        return None


def subir_a_drive(file_bytes: bytes, filename: str, empresa: str) -> str:
    """Sube un archivo PDF a la carpeta de la empresa en Drive. Retorna link o ''."""
    svc = _drive_service()
    if not svc:
        return ""
    folder_id = _obtener_o_crear_carpeta(empresa)
    if not folder_id:
        return ""
    try:
        from googleapiclient.http import MediaIoBaseUpload

        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype="application/pdf")
        meta = {"name": filename, "parents": [folder_id]}
        f = (
            svc.files()
            .create(body=meta, media_body=media, fields="id,webViewLink")
            .execute()
        )
        link = f.get("webViewLink", "")
        return link
    except Exception as e:
        st.warning(f"Error al subir a Drive: {e}")
        return ""


def drive_disponible() -> bool:
    return bool(os.environ.get("GOOGLE_SA_JSON", ""))


# ─── ESTILOS ──────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
    /* ── Fondo global blanco ── */
    [data-testid="stSidebar"] {display:none;}
    html, body, .stApp, [data-testid="stAppViewContainer"],
    [data-testid="stMain"], section.main, .block-container {
        background:#ffffff !important;
        color:#1a1a2e !important;
    }

    /* ── Tarjeta de login ── */
    .login-card {
        background:#ffffff;
        border-radius:20px;
        border:1.5px solid #e0e4ef;
        box-shadow:0 8px 40px rgba(192,57,43,.10);
        padding:44px 52px;
        width:100%;max-width:480px;
        margin:0 auto;
    }
    .login-card h2{color:#1a1a2e;margin:12px 0 4px;font-size:1.8rem;}
    .login-card p {color:#6b7280;margin:0 0 24px;font-size:.93rem;}

    /* ── Page header ── */
    .ph{
        background:linear-gradient(135deg,#c0392b,#922b21);
        border-radius:12px;padding:18px 26px;margin-bottom:20px;
        border-left:none;
    }
    .ph h1{color:#fff!important;margin:0;font-size:1.65rem;}
    .ph p {color:rgba(255,255,255,.8)!important;margin:4px 0 0;font-size:.9rem;}

    /* ── Barra superior ── */
    .topbar-wrap{
        background:#fff;border-bottom:2px solid #c0392b;
        padding:10px 0 12px;margin-bottom:20px;
    }

    /* ── Tarjetas de estado ── */
    .cv{background:#eafaf1;border-left:5px solid #27ae60;
        border-radius:10px;padding:12px 16px;margin:6px 0;}
    .cr{background:#fdf0ef;border-left:5px solid #e74c3c;
        border-radius:10px;padding:12px 16px;margin:6px 0;}
    .cv *{color:#145a32!important;margin:1px 0;}
    .cr *{color:#7b241c!important;margin:1px 0;}

    /* ── Badges ── */
    .bok{background:#27ae60;color:#fff!important;padding:2px 10px;border-radius:10px;font-size:.75rem;font-weight:700;}
    .bno{background:#e74c3c;color:#fff!important;padding:2px 10px;border-radius:10px;font-size:.75rem;font-weight:700;}
    .bwa{background:#f39c12;color:#fff!important;padding:2px 10px;border-radius:10px;font-size:.75rem;font-weight:700;}

    /* ── Encabezados de tabla ── */
    .row-header{
        font-size:.75rem;color:#6b7280;font-weight:700;
        text-transform:uppercase;letter-spacing:.5px;
        padding:5px 3px 2px;border-bottom:2px solid #e5e7eb;margin:0;
    }

    /* ── Métricas ── */
    div[data-testid="metric-container"]{
        background:#fafafa;border-radius:10px;padding:14px;
        border:1.5px solid #e5e7eb;
    }
    div[data-testid="metric-container"] label{color:#6b7280!important;}
    div[data-testid="metric-container"] [data-testid="stMetricValue"]{color:#1a1a2e!important;}

    /* ── Botón primario ── */
    .stButton button[kind="primary"]{
        background:linear-gradient(135deg,#c0392b,#922b21)!important;
        border:none!important;color:#fff!important;font-weight:700!important;
    }

    /* ── Títulos h3 ── */
    h3{border-bottom:2px solid #c0392b;padding-bottom:5px;color:#1a1a2e;}

    /* ── Etiquetas de uploader ── */
    .uploader-label{
        font-size:.78rem;font-weight:700;color:#6b7280;
        text-transform:uppercase;letter-spacing:.4px;margin-bottom:3px;
    }

    /* ── Fechas ── */
    .date-ok {color:#27ae60;font-size:.8rem;font-weight:700;}
    .date-bad{color:#e74c3c;font-size:.8rem;font-weight:700;}
    .date-na {color:#9ca3af;font-size:.8rem;}

    /* ── Separadores ── */
    hr{border-color:#e5e7eb !important;}

    /* ── Sidebar ── */
    [data-testid="stSidebar"]{background:#fafafa!important;}
    [data-testid="stSidebar"] *{color:#1a1a2e!important;}
    [data-testid="stSidebar"] hr{border-color:#e5e7eb!important;}

    /* ── Inputs ── */
    .stTextInput input, .stSelectbox select,
    [data-baseweb="input"] input, [data-baseweb="select"] {
        background:#fff!important;color:#1a1a2e!important;
        border-color:#d1d5db!important;
    }

    /* ── Expander ── */
    [data-testid="stExpander"]{
        border:1px solid #e5e7eb!important;
        border-radius:10px!important;
        background:#fafafa!important;
    }

    /* ── Tabs ── */
    button[data-baseweb="tab"]{color:#6b7280!important;}
    button[data-baseweb="tab"][aria-selected="true"]{
        color:#c0392b!important;border-bottom:2px solid #c0392b!important;
    }

    /* ── Dataframe ── */
    [data-testid="stDataFrame"]{border:1px solid #e5e7eb;border-radius:8px;}
</style>
""",
    unsafe_allow_html=True,
)


# Columnas requeridas en todo DataFrame de contratistas
COLS_REQUERIDAS = [
    "Empresa", "Nombre", "Cedula", "Antecedentes",
    "Fecha_Induccion", "Fecha_Caducidad", "Calificacion",
    "IESS_Mes", "Col8", "IESS_Detalle", "Col10", "Col11", "Col12",
    "Cert_Inicio", "Cert_Fin",
    "Fuente", "Horario", "Fecha_Fin_Trabajo",
    "PDF_IESS", "PDF_Salud", "PDF_Riesgos", "PDF_CedulaID",
    "Caducidad_IESS", "Caducidad_Salud", "Caducidad_Riesgos", "Caducidad_Cedula",
    "Aprobado_Planta", "Aprobado_SST", "Solicitante",
]

def _df_vacio():
    """DataFrame vacío con todas las columnas necesarias."""
    return pd.DataFrame(columns=COLS_REQUERIDAS)


# ─── CARGA DE DATOS ───────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def cargar_contratistas():
    url = f"https://docs.google.com/spreadsheets/d/{GS_CONTRATISTAS}/export?format=csv"
    # skiprows=5 salta las filas de metadatos; header=0 usa la fila 5 como encabezado
    df = pd.read_csv(url, skiprows=5, header=0, dtype=str)
    # Renombrar por posición para ser robusto a variaciones menores del título
    col_map = {
        df.columns[0]: "Empresa",
        df.columns[1]: "Nombre",
        df.columns[2]: "Cedula",
        df.columns[3]: "Antecedentes",
        df.columns[4]: "Fecha_Induccion",
        df.columns[5]: "Fecha_Caducidad",
        df.columns[6]: "Calificacion",
        df.columns[7]: "IESS_Mes",
        df.columns[8]: "Col8",
        df.columns[9]: "IESS_Detalle",
        df.columns[10]: "Col10",
        df.columns[11]: "Col11",
        df.columns[12]: "Col12",
        df.columns[13]: "Cert_Inicio",
        df.columns[14]: "Cert_Fin",
    }
    df = df.rename(columns=col_map)
    # Mantener solo las primeras 15 columnas relevantes
    df = df[[c for c in df.columns if c in col_map.values()]].copy()
    df = df[df["Empresa"].notna() & df["Nombre"].notna()].copy()
    df = df[~df["Empresa"].astype(str).str.lower().isin(["empresa", "nan", ""])].copy()
    df["Empresa"] = df["Empresa"].astype(str).str.strip()
    df["Nombre"] = df["Nombre"].astype(str).str.strip()
    df["Cedula"] = df["Cedula"].astype(str).str.strip()
    df["Fecha_Caducidad"] = pd.to_datetime(df["Fecha_Caducidad"], errors="coerce")
    df["Fecha_Induccion"] = pd.to_datetime(df["Fecha_Induccion"], errors="coerce")
    # Calificacion como número
    df["Calificacion"] = pd.to_numeric(df["Calificacion"], errors="coerce")
    df["Fuente"] = "Google Sheets"
    df["Horario"] = ""
    df["Fecha_Fin_Trabajo"] = pd.NaT
    for c in [
        "PDF_IESS", "PDF_Salud", "PDF_Riesgos", "PDF_CedulaID",
        "Caducidad_IESS", "Caducidad_Salud", "Caducidad_Riesgos", "Caducidad_Cedula",
    ]:
        df[c] = ""
    df["Aprobado_Planta"] = True
    df["Aprobado_SST"] = True
    df["Solicitante"] = ""
    return df


@st.cache_data(ttl=60)
def cargar_usuarios(sheet):
    from urllib.parse import quote
    url = (
        f"https://docs.google.com/spreadsheets/d/{GS_USUARIOS}"
        f"/export?format=csv&sheet={quote(sheet)}"
    )
    df = pd.read_csv(url, header=None, dtype=str)
    # Detectar fila de encabezado: buscar la fila cuya primera celda sea exactamente "Usuario"
    header_row = None
    for i, row in df.iterrows():
        vals = [str(v).strip().lower() for v in row.values]
        if "usuario" in vals:
            header_row = i
            break
    if header_row is None:
        header_row = 0
    df = df.iloc[header_row + 1:].reset_index(drop=True)
    ncols = len(df.columns)
    if ncols >= 3:
        df = df.iloc[:, :3]
        df.columns = ["Usuario", "Clave", "Correo"]
    else:
        df = df.iloc[:, :2]
        df.columns = ["Usuario", "Clave"]
        df["Correo"] = ""
    df = df[df["Usuario"].notna()].copy()
    df["Usuario"] = df["Usuario"].astype(str).str.strip()
    df["Clave"] = df["Clave"].astype(str).str.strip()
    df["Correo"] = df["Correo"].astype(str).str.strip()
    df["Correo"] = df["Correo"].replace({"nan": "", "NaN": "", "none": "", "None": ""})
    df = df[~df["Usuario"].str.lower().isin(["", "nan", "usuario", "none"])].copy()
    return df


def verificar_login(sheet, usuario, clave):
    try:
        df = cargar_usuarios(sheet)
        match = df[(df["Usuario"] == usuario) & (df["Clave"] == clave)]
        return not match.empty
    except Exception as e:
        st.error(f"Error al verificar credenciales: {e}")
        return False


@st.cache_data(ttl=60)
def cargar_supervisores(sheet):
    """Retorna lista de nombres y dict {nombre: correo} para el dropdown."""
    try:
        df = cargar_usuarios(sheet)
        nombres = sorted(df["Usuario"].tolist())
        correos = dict(zip(df["Usuario"], df["Correo"]))
        return nombres, correos
    except Exception:
        return [], {}


@st.cache_data(ttl=60)
def cargar_supervisores_desde_qp():
    """
    Lee la pestaña QP y retorna TODOS los usuarios en ambas listas desplegables.
    Retorna (nombres_planta, correos_planta, nombres_si, correos_si).
    """
    url = (
        f"https://docs.google.com/spreadsheets/d/{GS_USUARIOS}"
        f"/export?format=csv&sheet=QP"
    )
    try:
        raw = pd.read_csv(url, header=None, dtype=str)
        # Estructura: fila 0 = título, fila 1 = cabecera, fila 2+ = datos
        # Buscar la fila que tiene "Usuario" como cabecera
        header_idx = 0
        for i, row in raw.iterrows():
            if any(str(v).strip().lower() == "usuario" for v in row.values):
                header_idx = i
                break
        datos = raw.iloc[header_idx + 1:].reset_index(drop=True)
        # Columnas: 0=Usuario, 1=Clave, 2=Correo, 3=Departamento
        datos.columns = range(len(datos.columns))
        usuarios = datos[0].astype(str).str.strip()
        correos  = datos[2].astype(str).str.strip() if len(datos.columns) > 2 else pd.Series([""] * len(datos))
        # Limpiar valores vacíos o "nan"
        mask = ~usuarios.str.lower().isin(["", "nan", "usuario", "none"])
        usuarios = usuarios[mask].reset_index(drop=True)
        correos  = correos[mask].reset_index(drop=True)
        correos  = correos.replace({"nan": "", "NaN": "", "none": ""})
        nombres = sorted(usuarios.tolist())
        correos_dict = dict(zip(usuarios, correos))
        # Todos los nombres van en ambas listas
        return nombres, correos_dict, nombres, correos_dict
    except Exception:
        return [], {}, [], {}


def enviar_email_supervisores(
    emails_dest, empresa, supervisores_sel, num_personas, pdfs_bytes
):
    """Envía correo con los PDFs adjuntos a los supervisores seleccionados."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.application import MIMEApplication

    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")

    if not smtp_host or not smtp_user:
        return False, "Variables SMTP_HOST / SMTP_USER no configuradas"

    destinatarios = [e for e in emails_dest if e and "@" in e]
    if not destinatarios:
        return False, "No se encontraron correos válidos para los supervisores"

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = ", ".join(destinatarios)
        msg["Subject"] = f"[Security Access] Solicitud de ingreso — {empresa}"

        cuerpo = f"""
<html><body style="font-family:Arial,sans-serif;color:#1a1a2e">
<h2 style="color:#c0392b">🏭 Quimpac Ecuador S.A. — Security Access</h2>
<p>Se ha enviado una nueva solicitud de ingreso que requiere su aprobación:</p>
<table style="border-collapse:collapse;width:100%">
  <tr><td style="padding:6px;font-weight:bold">Empresa:</td><td>{empresa}</td></tr>
  <tr><td style="padding:6px;font-weight:bold">N° trabajadores:</td><td>{num_personas}</td></tr>
  <tr><td style="padding:6px;font-weight:bold">Supervisores:</td><td>{", ".join(supervisores_sel)}</td></tr>
</table>
<p style="margin-top:16px">Se adjuntan los documentos PDF de los trabajadores para su revisión.</p>
<p>Por favor ingrese al sistema <b>Security Access</b> para aprobar o rechazar la solicitud.</p>
<hr><p style="font-size:.8rem;color:#6b7280">Mensaje automático — Quimpac Ecuador S.A.</p>
</body></html>"""
        msg.attach(MIMEText(cuerpo, "html"))

        for nombre_pdf, bytes_pdf in pdfs_bytes.items():
            if bytes_pdf:
                part = MIMEApplication(bytes_pdf, Name=nombre_pdf)
                part["Content-Disposition"] = f'attachment; filename="{nombre_pdf}"'
                msg.attach(part)

        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.starttls()
            s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, destinatarios, msg.as_string())
        return True, f"Correo enviado a: {', '.join(destinatarios)}"
    except Exception as e:
        return False, str(e)


# ─── PDF: EXTRACCIÓN DE FECHAS ────────────────────────────────────────────────
PATRONES_CADUCIDAD = [
    r"(?:v[aá]lid[ao]\s+hasta|vigente\s+hasta|caducidad|vencimiento|expira(?:ci[oó]n)?|fecha\s+de\s+vencimiento)[^\d]{0,15}(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
    r"(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
]
PATRONES_EMISION = [
    r"(?:fecha\s+de\s+emisi[oó]n|emitido\s+el|fecha\s+de\s+inicio)[^\d]{0,15}(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
]


def extraer_fechas_pdf(pdf_bytes):
    """Extrae fechas del PDF e intenta identificar la fecha de caducidad."""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            texto = "\n".join(p.extract_text() or "" for p in pdf.pages).lower()

        fechas_cad = []
        for pat in PATRONES_CADUCIDAD:
            for m in re.finditer(pat, texto, re.IGNORECASE):
                raw = m.group(1)
                for fmt in ["%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y"]:
                    try:
                        fechas_cad.append(
                            datetime.strptime(
                                raw.replace("-", "/").replace(".", "/"), fmt
                            ).date()
                        )
                        break
                    except Exception:
                        pass

        if fechas_cad:
            return max(fechas_cad)
    except Exception:
        pass
    return None


def guardar_archivo(uploaded_file, carpeta, prefijo):
    """Guarda archivo subido localmente y retorna la ruta."""
    try:
        os.makedirs(f"{UPLOADS_DIR}/{carpeta}", exist_ok=True)
        nombre = f"{prefijo}_{uploaded_file.name}"
        ruta = f"{UPLOADS_DIR}/{carpeta}/{nombre}"
        with open(ruta, "wb") as f:
            f.write(uploaded_file.getvalue())
        return ruta
    except Exception:
        return ""


def estado_fecha(fecha_str):
    """Devuelve HTML con estado de la fecha de caducidad."""
    if not fecha_str or fecha_str == "—":
        return "<span class='date-na'>Sin datos</span>"
    try:
        if isinstance(fecha_str, str):
            d = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        else:
            d = fecha_str
        hoy = date.today()
        if d >= hoy:
            diff = (d - hoy).days
            return f"<span class='date-ok'>✅ Vigente hasta {d.strftime('%d/%m/%Y')} ({diff}d)</span>"
        else:
            return f"<span class='date-bad'>❌ Caducado {d.strftime('%d/%m/%Y')}</span>"
    except Exception:
        return f"<span class='date-na'>{fecha_str}</span>"


# ─── SESSION STATE ────────────────────────────────────────────────────────────
defaults = {
    "logged_in": False,
    "rol": None,
    "usuario": "",
    "modulo": None,
    "nuevos_contratistas": pd.DataFrame(),
    "log_accesos": pd.DataFrame(
        columns=["Timestamp", "Cedula", "Nombre", "Empresa", "Resultado", "Operador"]
    ),
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ─── HELPERS ─────────────────────────────────────────────────────────────────
def get_db_completa():
    try:
        base = cargar_contratistas()
    except Exception:
        base = _df_vacio()
    if base.empty:
        base = _df_vacio()
    nuevos = st.session_state.nuevos_contratistas
    if not nuevos.empty:
        return pd.concat([base, nuevos], ignore_index=True)
    return base


def evaluar(fila):
    """
    Reglas de acceso:
      1. Calificación Inducción >= 60
      2. Fecha de Caducidad en el futuro (>= hoy)
      3. Si es solicitud nueva: aprobación de Supervisor Planta Y Seguridad Industrial
    """
    motivos = []
    hoy = pd.Timestamp(date.today())

    # ── 1. Fecha de caducidad ──────────────────────────────────────────────
    cad = fila.get("Fecha_Caducidad") if isinstance(fila, dict) else fila["Fecha_Caducidad"]
    try:
        cad_ts = pd.Timestamp(cad)
        if pd.isna(cad_ts) or cad_ts < hoy:
            motivos.append("❌ Fecha de caducidad vencida o sin fecha")
    except Exception:
        motivos.append("❌ Fecha de caducidad inválida")

    # ── 2. Calificación Inducción >= 60 ────────────────────────────────────
    cal = fila.get("Calificacion") if isinstance(fila, dict) else fila.get("Calificacion")
    try:
        cal_num = float(cal) if cal not in (None, "", "nan") else None
    except (ValueError, TypeError):
        cal_num = None
    if cal_num is None:
        motivos.append("❌ Sin calificación de inducción registrada")
    elif cal_num < 60:
        motivos.append(f"❌ Calificación de inducción insuficiente ({cal_num:.0f}/100 — mínimo 60)")

    # ── 3. Aprobaciones (solo para solicitudes nuevas, no historial Sheets) ─
    if str(fila.get("Fuente", "")) != "Google Sheets":
        if not fila.get("Aprobado_Planta", False):
            motivos.append("⚠️ Pendiente aprobación Supervisor de Planta")
        if not fila.get("Aprobado_SST", False):
            motivos.append("⚠️ Pendiente aprobación Supervisor Seg. Industrial")

    return len(motivos) == 0, motivos


def registrar_log(cedula, nombre, empresa, resultado, operador="Sistema"):
    nuevo = pd.DataFrame(
        [
            {
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Cedula": cedula,
                "Nombre": nombre,
                "Empresa": empresa,
                "Resultado": resultado,
                "Operador": operador,
            }
        ]
    )
    st.session_state.log_accesos = pd.concat(
        [st.session_state.log_accesos, nuevo], ignore_index=True
    )


MODULOS_POR_ROL = {
    "Contratista": ["📝 Solicitud de Ingreso"],
    "Seguridad Física": ["🏠 Dashboard", "🛡️ Verificación Garita", "📊 Registro de Accesos"],
    "Supervisor Planta": [
        "🏠 Dashboard",
        "✅ Gestión de Aprobaciones",
        "📊 Registro de Accesos",
    ],
    "Seguridad Industrial": [
        "🏠 Dashboard",
        "✅ Gestión de Aprobaciones",
        "📊 Registro de Accesos",
    ],
}


def topbar():
    rol_icon = {
        "Contratista": "📋",
        "Seguridad Física": "🛡️",
        "Supervisor Planta": "⚙️",
        "Seguridad Industrial": "🦺",
    }.get(st.session_state.rol, "")
    c1, c2, c3 = st.columns([1, 8, 2])
    with c1:
        if LOGO_B64:
            st.markdown(
                f"<img src='data:image/png;base64,{LOGO_B64}' style='height:44px;margin-top:4px;background:#fff;border-radius:6px;padding:2px'>",
                unsafe_allow_html=True,
            )
    with c2:
        st.markdown(
            f"<b style='color:#1a1a2e;font-size:1.05rem'>Security Access</b><br>"
            f"<span style='color:#6b7280;font-size:.82rem'>{rol_icon} {st.session_state.rol}"
            + (
                f" · <b style='color:#c0392b'>{st.session_state.usuario}</b>"
                if st.session_state.usuario
                else ""
            )
            + "</span>",
            unsafe_allow_html=True,
        )
    with c3:
        if st.button("🚪 Cerrar sesión", use_container_width=True):
            for k in ["logged_in", "rol", "usuario", "modulo"]:
                st.session_state[k] = False if k == "logged_in" else None
            st.rerun()
    st.markdown(
        "<hr style='margin:8px 0 20px;border-color:#e5e7eb'>", unsafe_allow_html=True
    )


def nav_sidebar(opciones):
    st.markdown(
        "<style>[data-testid='stSidebar']{display:flex!important;}</style>",
        unsafe_allow_html=True,
    )
    with st.sidebar:
        if LOGO_B64:
            st.markdown(
                f"<div style='text-align:center;padding:10px 0 4px'>"
                f"<img src='data:image/png;base64,{LOGO_B64}' style='max-width:160px'></div>",
                unsafe_allow_html=True,
            )
        st.markdown("## 🔐 Security Access")
        sel = st.radio(
            "",
            opciones,
            label_visibility="collapsed",
            index=opciones.index(st.session_state.modulo)
            if st.session_state.modulo in opciones
            else 0,
        )
        if sel != st.session_state.modulo:
            st.session_state.modulo = sel
            st.rerun()
        st.markdown("---")
        try:
            df = get_db_completa()
            hoy = pd.Timestamp(date.today())
            vig = df[pd.to_datetime(df["Fecha_Caducidad"], errors="coerce") >= hoy]
            st.metric("Total registros", len(df))
            st.metric("Inducción vigente", len(vig))
            st.metric("Empresas", df["Empresa"].nunique())
        except Exception:
            pass
        st.markdown(f"---\n📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}")


# ════════════════════════════════════════════════════════════════════════════════
# PANTALLA DE LOGIN
# ════════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    st.markdown(
        f"""
    <div style='text-align:center;padding:50px 0 0;background:#ffffff'>
        {'<img src="data:image/png;base64,' + LOGO_B64 + '" style="max-width:420px;width:85%;background:transparent">' if LOGO_B64 else '<h2 style="color:#c0392b">QUIMPAC ECUADOR</h2>'}
    </div>
    <div style='text-align:center;margin:28px 0 6px'>
        <hr style='border:none;border-top:2px solid #c0392b;margin:0 auto 16px;max-width:520px'>
        <span style='font-size:1.4rem;font-weight:700;color:#1a1a2e;letter-spacing:.10em'>SECURITY ACCESS</span>
        <hr style='border:none;border-top:2px solid #c0392b;margin:16px auto 0;max-width:520px'>
    </div>
    <p style='text-align:center;color:#6b7280;font-size:.95rem;margin:10px 0 22px'>
        Seleccione su perfil para iniciar sesión
    </p>""",
        unsafe_allow_html=True,
    )

    col = st.columns([1, 1.3, 1])[1]
    with col:
        rol_sel = st.selectbox(
            "Tipo de acceso",
            [
                "— Seleccione —",
                "Contratista",
                "Seguridad Física",
                "Supervisor Planta",
                "Seguridad Industrial",
            ],
        )

        if rol_sel == "Contratista":
            st.info("ℹ️ El acceso de Contratista no requiere contraseña.")
            if st.button(
                "▶ Ingresar como Contratista", type="primary", use_container_width=True
            ):
                st.session_state.update(
                    {
                        "logged_in": True,
                        "rol": "Contratista",
                        "usuario": "Contratista",
                        "modulo": "📝 Solicitud de Ingreso",
                    }
                )
                st.rerun()

        elif rol_sel in ("Seguridad Física", "Supervisor Planta", "Seguridad Industrial"):
            sheet_map = {
                "Seguridad Física": "Seguridad",
                "Supervisor Planta": "QP",
                "Seguridad Industrial": "Seg. Industrial",
            }
            st.markdown("<br>", unsafe_allow_html=True)
            u_inp = st.text_input("Usuario", placeholder="Ingrese su usuario")
            p_inp = st.text_input("Contraseña", type="password", placeholder="••••••••")

            if st.button("🔐 Iniciar Sesión", type="primary", use_container_width=True):
                if not u_inp or not p_inp:
                    st.error("Complete usuario y contraseña.")
                elif verificar_login(sheet_map[rol_sel], u_inp.strip(), p_inp.strip()):
                    st.session_state.update(
                        {
                            "logged_in": True,
                            "rol": rol_sel,
                            "usuario": u_inp.strip(),
                            "modulo": "🏠 Dashboard",
                        }
                    )
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos.")

    st.stop()

# ════════════════════════════════════════════════════════════════════════════════
# LAYOUT AUTENTICADO
# ════════════════════════════════════════════════════════════════════════════════
ROL = st.session_state.rol
opciones_nav = MODULOS_POR_ROL.get(ROL, [])
if st.session_state.modulo not in opciones_nav:
    st.session_state.modulo = opciones_nav[0] if opciones_nav else None

topbar()
nav_sidebar(opciones_nav)
modulo = st.session_state.modulo

# ════════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════════════════════════════
if modulo == "🏠 Dashboard":
    st.markdown(
        """<div class='ph'><h1>🏠 Dashboard General</h1>
    <p>Quimpac Ecuador S.A. · Sistema de control de accesos para contratistas</p></div>""",
        unsafe_allow_html=True,
    )

    with st.spinner("Cargando base de datos Google Sheets..."):
        df = get_db_completa()

    hoy = pd.Timestamp(date.today())
    df["_cad"] = pd.to_datetime(df["Fecha_Caducidad"], errors="coerce")
    vigentes = df[df["_cad"] >= hoy]
    caducados = df[df["_cad"] < hoy]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👷 Total registros", len(df))
    c2.metric("✅ Inducción vigente", len(vigentes))
    c3.metric("⚠️ Inducción caducada", len(caducados))
    c4.metric("🏢 Empresas activas", df["Empresa"].nunique())

    st.markdown("---")
    col_izq, col_der = st.columns([3, 2])

    with col_izq:
        st.markdown("### 📋 Nuevas solicitudes del sistema")
        nuevos = st.session_state.nuevos_contratistas
        if nuevos.empty:
            st.info(
                "Sin solicitudes nuevas. Los datos históricos provienen de Google Sheets."
            )
        else:
            for _, fila in nuevos.iterrows():
                ok, motivos = evaluar(fila)
                nombre = str(fila.get("Nombre", ""))
                empresa = str(fila.get("Empresa", ""))
                cedula = str(fila.get("Cedula", ""))
                horario = str(fila.get("Horario", ""))
                if ok:
                    st.markdown(
                        f"""<div class='cv'>
                        <p><b>🟢 {nombre}</b> &nbsp;<span class='bok'>HABILITADO</span></p>
                        <p style='font-size:.85rem'>🏢 {empresa} | 🆔 {cedula} | ⏰ {horario}</p>
                    </div>""",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"""<div class='cr'>
                        <p><b>🔴 {nombre}</b> &nbsp;<span class='bno'>PENDIENTE APROBACIÓN</span></p>
                        <p style='font-size:.85rem'>🏢 {empresa} | 🆔 {cedula}</p>
                        <p style='font-size:.82rem'>{"  ·  ".join(motivos)}</p>
                    </div>""",
                        unsafe_allow_html=True,
                    )

    with col_der:
        st.markdown("### 📌 Top empresas (Google Sheets)")
        top = (
            df.groupby("Empresa")
            .agg(
                Total=("Nombre", "count"), Vigentes=("_cad", lambda x: (x >= hoy).sum())
            )
            .reset_index()
            .sort_values("Total", ascending=False)
            .head(15)
        )
        top["Caducados"] = top["Total"] - top["Vigentes"]
        st.dataframe(top, use_container_width=True, hide_index=True)

        st.markdown("### ⏰ Próximas a caducar (30 días)")
        prox = (
            df[(df["_cad"] >= hoy) & (df["_cad"] <= hoy + pd.Timedelta(days=30))][
                ["Empresa", "Nombre", "Cedula", "_cad"]
            ]
            .rename(columns={"_cad": "Caduca"})
            .head(10)
        )
        if prox.empty:
            st.success("✅ Ninguna en los próximos 30 días.")
        else:
            st.dataframe(prox, use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════════════════════════════
# SOLICITUD DE INGRESO (CONTRATISTAS)
# ════════════════════════════════════════════════════════════════════════════════
elif modulo == "📝 Solicitud de Ingreso":
    st.markdown(
        """<div class='ph'><h1>📝 Solicitud de Ingreso — Contratistas</h1>
    <p>Registre los datos de la empresa, fechas de trabajo, documentos y personal autorizado</p></div>""",
        unsafe_allow_html=True,
    )

    # ── Sección: Datos de la solicitud ──────────────────────────────────────
    st.markdown("### 🏢 Datos de la solicitud")

    # Cargar supervisores desde pestaña QP, separados por departamento
    sup_qp_lista, sup_qp_correos, sup_si_lista, sup_si_correos = cargar_supervisores_desde_qp()

    ca, cb = st.columns([3, 3])
    empresa = ca.text_input(
        "Empresa / Razón social *", placeholder="Ej: TechMaint S.A."
    )

    cc, cd = st.columns([2, 2])
    f_ingreso = cc.date_input("Fecha de ingreso *", value=date.today())
    f_salida = cd.date_input("Fecha de salida estimada *", value=date.today())

    sa, sb = st.columns([3, 3])
    opciones_qp = ["— Seleccione supervisor —"] + sup_qp_lista
    sup_planta_sel = sa.selectbox("👔 Supervisor de Planta que autoriza *", opciones_qp)
    supervisor = sup_planta_sel if sup_planta_sel != opciones_qp[0] else ""

    opciones_si = ["— Seleccione supervisor —"] + sup_si_lista
    sup_si_sel = sb.selectbox(
        "🦺 Supervisor Seg. Industrial que autoriza *", opciones_si
    )
    supervisor_si = sup_si_sel if sup_si_sel != opciones_si[0] else ""

    # ── Preview de correos detectados ────────────────────────────────────────
    smtp_ok = bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER"))
    if smtp_ok and (supervisor or supervisor_si):
        em1, em2 = st.columns(2)
        if supervisor:
            ep = sup_qp_correos.get(supervisor, "")
            em1.markdown(
                f"<span style='font-size:.8rem'>📧 Planta: <b style='color:{'#27ae60' if ep else '#e74c3c'}'>"
                f"{'No hay correo registrado' if not ep else ep}</b></span>",
                unsafe_allow_html=True,
            )
        if supervisor_si:
            es = sup_si_correos.get(supervisor_si, "")
            em2.markdown(
                f"<span style='font-size:.8rem'>📧 Seg. Ind.: <b style='color:{'#27ae60' if es else '#e74c3c'}'>"
                f"{'No hay correo registrado' if not es else es}</b></span>",
                unsafe_allow_html=True,
            )

    descripcion = st.text_area(
        "Descripción del trabajo a realizar",
        placeholder="Ej: Mantenimiento preventivo de compresores — Área de producción.",
        height=70,
    )

    # ── Sección: Documentos generales de la empresa ──────────────────────────
    st.markdown("### 📂 Documentos de análisis de riesgos (empresa)")
    dr1, dr2 = st.columns(2)
    with dr1:
        st.markdown(
            "<p class='uploader-label'>📋 Análisis de Riesgos Laborales</p>",
            unsafe_allow_html=True,
        )
        doc_riesgos_lab = st.file_uploader(
            "", type=["pdf"], key="doc_riesgos_lab", label_visibility="collapsed"
        )
    with dr2:
        st.markdown(
            "<p class='uploader-label'>🌿 Análisis de Riesgos Ambientales</p>",
            unsafe_allow_html=True,
        )
        doc_riesgos_amb = st.file_uploader(
            "", type=["pdf"], key="doc_riesgos_amb", label_visibility="collapsed"
        )

    if doc_riesgos_lab:
        st.success(f"✅ Riesgos Laborales cargado: {doc_riesgos_lab.name}")
    if doc_riesgos_amb:
        st.success(f"✅ Riesgos Ambientales cargado: {doc_riesgos_amb.name}")

    # ── Estado de notificaciones ──────────────────────────────────────────────
    smtp_configurado = bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER"))
    if drive_disponible() and smtp_configurado:
        st.success("☁️ Google Drive conectado · 📧 Email configurado — Los PDFs se guardan en Drive y se notifica a supervisores automáticamente.")
    elif smtp_configurado:
        st.success("📧 Email configurado — Al enviar la solicitud, los supervisores recibirán los PDFs adjuntos por correo.")
    else:
        with st.expander("📧 ¿Cómo reciben los PDFs los supervisores? — Ver instrucciones", expanded=False):
            st.markdown("""
**Opción recomendada (gratuita): Gmail SMTP**

Configure estas 4 variables en **Secrets** de Replit (ícono 🔒 en el panel lateral):

| Variable | Valor |
|----------|-------|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | `su_correo@gmail.com` |
| `SMTP_PASS` | Contraseña de aplicación Gmail* |

> **\\*Contraseña de aplicación Gmail:** en su cuenta Google vaya a *Seguridad → Verificación en 2 pasos → Contraseñas de aplicación*, genere una para "Correo" y péguele aquí.

Una vez configurado, al enviar la solicitud los supervisores recibirán **automáticamente un correo con los PDFs adjuntos**.
""")
        st.info("📁 Por ahora los archivos se guardan en el servidor. Configure las variables SMTP para activar el envío de correo.")

    # ── Sección: Listado de personal ─────────────────────────────────────────
    st.markdown("### 👷 Listado de personal (máximo 20 personas)")
    st.caption(
        "Complete nombre, cédula y horario de cada trabajador, luego cargue los documentos PDF correspondientes."
    )

    lista_personal = []

    for i in range(1, 21):
        with st.expander(f"👷 Persona N° {i}", expanded=(i <= 3)):
            # ── Datos básicos ────────────────────────────────────────────────
            t1, t2, t3 = st.columns([3, 2, 2])
            nom = t1.text_input(
                "Nombre Completo", key=f"nom_{i}", placeholder="Apellidos y Nombres"
            )
            ced = t2.text_input("Cédula / ID", key=f"ced_{i}", placeholder="0900000000")
            hor = t3.text_input("Horario", key=f"hor_{i}", placeholder="08:00 - 17:00")

            # ── Documentos PDF (siempre visibles) ────────────────────────────
            st.markdown(
                "<p style='color:#6b7280;font-size:.82rem;font-weight:600;"
                "margin:10px 0 6px;'>📄 Documentos requeridos — cargue el PDF de cada certificado:</p>",
                unsafe_allow_html=True,
            )

            p1, p2, p3, p4 = st.columns(4)
            with p1:
                st.markdown(
                    "<p class='uploader-label'>📌 Afiliación IESS</p>",
                    unsafe_allow_html=True,
                )
                f_iess = st.file_uploader(
                    "iess", type=["pdf"], key=f"iess_{i}", label_visibility="collapsed"
                )
            with p2:
                st.markdown(
                    "<p class='uploader-label'>🏥 Cert. Salud Ocupacional</p>",
                    unsafe_allow_html=True,
                )
                f_sal = st.file_uploader(
                    "sal", type=["pdf"], key=f"sal_{i}", label_visibility="collapsed"
                )
            with p3:
                st.markdown(
                    "<p class='uploader-label'>⚠️ Cert. Riesgos Laborales</p>",
                    unsafe_allow_html=True,
                )
                f_rie = st.file_uploader(
                    "rie", type=["pdf"], key=f"rie_{i}", label_visibility="collapsed"
                )
            with p4:
                st.markdown(
                    "<p class='uploader-label'>🪪 Cédula de Identidad</p>",
                    unsafe_allow_html=True,
                )
                f_ced = st.file_uploader(
                    "ced", type=["pdf"], key=f"fced_{i}", label_visibility="collapsed"
                )

            # ── Procesar cada PDF cargado ────────────────────────────────────
            def _proc_pdf(f_obj, tipo_doc, persona_num, emp_nombre):
                if f_obj is None:
                    return "", ""
                bytes_pdf = f_obj.getvalue()
                fecha_cad = extraer_fechas_pdf(bytes_pdf)
                fecha_str = str(fecha_cad) if fecha_cad else ""
                # Intentar subir a Drive primero
                nombre_archivo = f"{_normalizar(emp_nombre or 'empresa')}_{tipo_doc}_P{persona_num}_{f_obj.name}"
                link_drive = subir_a_drive(
                    bytes_pdf, nombre_archivo, emp_nombre or "empresa"
                )
                if link_drive:
                    return link_drive, fecha_str
                # Fallback local
                ruta = guardar_archivo(
                    f_obj, _normalizar(emp_nombre or "empresa"), tipo_doc
                )
                return ruta, fecha_str

            emp_actual = empresa.strip() if empresa.strip() else "empresa"
            link_iess, cad_iess = _proc_pdf(f_iess, "IESS", i, emp_actual)
            link_sal, cad_sal = _proc_pdf(f_sal, "Salud", i, emp_actual)
            link_rie, cad_rie = _proc_pdf(f_rie, "Riesgos", i, emp_actual)
            link_ced, cad_ced = _proc_pdf(f_ced, "Cedula", i, emp_actual)

            # ── Estado de fechas extraídas ───────────────────────────────────
            any_loaded = any([f_iess, f_sal, f_rie, f_ced])
            if any_loaded:
                st.markdown(
                    "<p style='font-size:.78rem;color:#6b7280;margin:8px 0 2px'>📅 Validez detectada en los PDFs:</p>",
                    unsafe_allow_html=True,
                )
                e1, e2, e3, e4 = st.columns(4)
                e1.markdown(
                    estado_fecha(cad_iess)
                    if f_iess
                    else "<span class='date-na'>—</span>",
                    unsafe_allow_html=True,
                )
                e2.markdown(
                    estado_fecha(cad_sal)
                    if f_sal
                    else "<span class='date-na'>—</span>",
                    unsafe_allow_html=True,
                )
                e3.markdown(
                    estado_fecha(cad_rie)
                    if f_rie
                    else "<span class='date-na'>—</span>",
                    unsafe_allow_html=True,
                )
                e4.markdown(
                    estado_fecha(cad_ced)
                    if f_ced
                    else "<span class='date-na'>—</span>",
                    unsafe_allow_html=True,
                )

            # ── Acumular si tiene nombre ─────────────────────────────────────
            if nom.strip():
                lista_personal.append(
                    {
                        "Empresa": empresa,
                        "Solicitante": supervisor,
                        "Nombre": nom.strip(),
                        "Cedula": ced.strip(),
                        "Horario": hor.strip(),
                        "Fecha_Induccion": pd.Timestamp(f_ingreso),
                        "Fecha_Caducidad": pd.Timestamp(f_salida),
                        "Fecha_Fin_Trabajo": pd.Timestamp(f_salida),
                        "PDF_IESS": link_iess,
                        "PDF_Salud": link_sal,
                        "PDF_Riesgos": link_rie,
                        "PDF_CedulaID": link_ced,
                        "Caducidad_IESS": cad_iess,
                        "Caducidad_Salud": cad_sal,
                        "Caducidad_Riesgos": cad_rie,
                        "Caducidad_Cedula": cad_ced,
                        # Bytes en memoria para adjuntar al correo directamente
                        "_bytes_iess": f_iess.getvalue() if f_iess else b"",
                        "_bytes_sal":  f_sal.getvalue()  if f_sal  else b"",
                        "_bytes_rie":  f_rie.getvalue()  if f_rie  else b"",
                        "_bytes_ced":  f_ced.getvalue()  if f_ced  else b"",
                        "_fname_iess": f_iess.name if f_iess else "",
                        "_fname_sal":  f_sal.name  if f_sal  else "",
                        "_fname_rie":  f_rie.name  if f_rie  else "",
                        "_fname_ced":  f_ced.name  if f_ced  else "",
                        "Aprobado_Planta": False,
                        "Aprobado_SST": False,
                        "Fuente": "Solicitud",
                        "Calificacion": "",
                        "IESS_Mes": "",
                        "Antecedentes": "",
                        "Col8": "",
                        "IESS_Detalle": "",
                        "Col10": "",
                        "Col11": "",
                        "Col12": "",
                        "Cert_Inicio": "",
                        "Cert_Fin": "",
                        "Observaciones": "",
                    }
                )

    st.markdown("---")
    if st.button(
        "🚀 Enviar Solicitud de Ingreso", type="primary", use_container_width=True
    ):
        if not empresa.strip():
            st.error("❌ Ingrese el nombre de la empresa.")
        elif not supervisor:
            st.error("❌ Seleccione el Supervisor de Planta.")
        elif not supervisor_si:
            st.error("❌ Seleccione el Supervisor de Seguridad Industrial.")
        elif len(lista_personal) == 0:
            st.error("❌ Complete el nombre de al menos una persona.")
        else:
            emp_actual = empresa.strip()
            # Subir documentos de empresa (riesgos)
            if doc_riesgos_lab:
                b = doc_riesgos_lab.getvalue()
                fn = (
                    f"{_normalizar(emp_actual)}_RiesgosLaborales_{doc_riesgos_lab.name}"
                )
                subir_a_drive(b, fn, emp_actual) or guardar_archivo(
                    doc_riesgos_lab, _normalizar(emp_actual), "RiesgosLaborales"
                )
            if doc_riesgos_amb:
                b = doc_riesgos_amb.getvalue()
                fn = f"{_normalizar(emp_actual)}_RiesgosAmbientales_{doc_riesgos_amb.name}"
                subir_a_drive(b, fn, emp_actual) or guardar_archivo(
                    doc_riesgos_amb, _normalizar(emp_actual), "RiesgosAmbientales"
                )

            nuevos_df = pd.DataFrame(lista_personal)
            nuevos_df["Supervisor_SI"] = supervisor_si
            st.session_state.nuevos_contratistas = pd.concat(
                [st.session_state.nuevos_contratistas, nuevos_df], ignore_index=True
            )

            destino = "Google Drive ☁️" if drive_disponible() else "servidor local 💾"
            st.success(
                f"✅ Solicitud enviada: **{len(lista_personal)} persona(s)** · Empresa: **{emp_actual}** · Período: {f_ingreso} → {f_salida}"
            )
            st.success(f"📁 Documentos guardados en: {destino}")
            st.info(
                "🔔 El acceso se habilitará cuando Planta y Seg. Industrial aprueben en Gestión de Aprobaciones."
            )

            # ── Envío de correo a supervisores ───────────────────────────────
            email_planta = sup_qp_correos.get(supervisor, "")
            email_si = sup_si_correos.get(supervisor_si, "")
            emails_dest = list({e for e in [email_planta, email_si] if e and "@" in e})

            # Recopilar PDFs directamente desde bytes en memoria (sin leer disco)
            pdfs_para_correo = {}
            for p in lista_personal:
                nom_lim = re.sub(r"[^\w]", "_", p["Nombre"])[:20]
                for campo_bytes, campo_fname, label in [
                    ("_bytes_iess", "_fname_iess", "IESS"),
                    ("_bytes_sal",  "_fname_sal",  "Salud"),
                    ("_bytes_rie",  "_fname_rie",  "Riesgos"),
                    ("_bytes_ced",  "_fname_ced",  "Cedula"),
                ]:
                    b = p.get(campo_bytes, b"")
                    fn = p.get(campo_fname, "") or f"{label}.pdf"
                    if b:
                        pdfs_para_correo[f"{nom_lim}_{label}_{fn}"] = b

            smtp_act = bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER"))
            if not smtp_act:
                st.info("ℹ️ Correo no enviado: configure las variables SMTP en Secrets para activar notificaciones.")
            elif not emails_dest:
                ep_disp = email_planta if email_planta else "sin correo"
                es_disp = email_si if email_si else "sin correo"
                st.warning(
                    f"⚠️ No se encontraron correos para los supervisores seleccionados "
                    f"(Planta: '{ep_disp}', SI: '{es_disp}'). "
                    "Verifique la columna Correo en el Google Sheet."
                )
            else:
                ok_mail, msg_mail = enviar_email_supervisores(
                    emails_dest,
                    emp_actual,
                    [supervisor, supervisor_si],
                    len(lista_personal),
                    pdfs_para_correo,
                )
                if ok_mail:
                    st.success(f"📧 Correo enviado correctamente a: {', '.join(emails_dest)} · {len(pdfs_para_correo)} PDF(s) adjuntos")
                else:
                    st.error(f"❌ Error al enviar correo: {msg_mail}")
            st.balloons()

# ════════════════════════════════════════════════════════════════════════════════
# VERIFICACIÓN EN GARITA
# ════════════════════════════════════════════════════════════════════════════════
elif modulo == "🛡️ Verificación Garita":
    st.markdown(
        """<div class='ph'><h1>🛡️ Verificación en Garita</h1>
    <p>Consulta en tiempo real · Busque por cédula, nombre o empresa</p></div>""",
        unsafe_allow_html=True,
    )

    guardia = st.text_input("👮 Guardia en turno:", placeholder="Ej: Sargento Ramírez")

    with st.spinner("Cargando base de datos..."):
        df_g = get_db_completa()

    tab_busq, tab_emp = st.tabs(["🔍 Buscar Nombre / Cédula", "🏢 Buscar por Empresa"])

    with tab_busq:
        busq = st.text_input(
            "Nombre o cédula:", placeholder="Ej: 0912345678 o Juan Pérez"
        )
        if busq.strip():
            mask = df_g["Nombre"].str.contains(busq, case=False, na=False) | df_g[
                "Cedula"
            ].str.contains(busq, na=False)
            res = df_g[mask].head(10)
            if res.empty:
                st.warning("⚠️ Persona no encontrada en el sistema.")
            else:
                for _, fila in res.iterrows():
                    ok, motivos = evaluar(fila)
                    nombre = str(fila["Nombre"])
                    empresa = str(fila["Empresa"])
                    cedula = str(fila["Cedula"])
                    horario = str(fila.get("Horario", "")) or "No especificado"
                    cad = fila.get("Fecha_Caducidad")
                    cad_str = (
                        str(pd.Timestamp(cad).date()) if pd.notna(cad) else "Sin datos"
                    )

                    if ok:
                        st.markdown(
                            f"""<div class='cv'>
                            <p><b>✅ ACCESO PERMITIDO — {nombre}</b></p>
                            <p>🏢 {empresa} | 🆔 {cedula} | ⏰ {horario}</p>
                            <p style='font-size:.85rem'>📅 Inducción válida hasta: <b>{cad_str}</b></p>
                        </div>""",
                            unsafe_allow_html=True,
                        )
                        registrar_log(
                            cedula, nombre, empresa, "PERMITIDO", guardia or "Garita"
                        )
                    else:
                        st.markdown(
                            f"""<div class='cr'>
                            <p><b>🚨 ACCESO DENEGADO — {nombre}</b></p>
                            <p>🏢 {empresa} | 🆔 {cedula}</p>
                        </div>""",
                            unsafe_allow_html=True,
                        )
                        for m in motivos:
                            st.error(m)
                        registrar_log(
                            cedula, nombre, empresa, "DENEGADO", guardia or "Garita"
                        )

                    # Documentos de solicitudes nuevas
                    pdfs = {
                        "IESS": fila.get("PDF_IESS", ""),
                        "Salud": fila.get("PDF_Salud", ""),
                        "Riesgos": fila.get("PDF_Riesgos", ""),
                        "Cédula": fila.get("PDF_CedulaID", ""),
                    }
                    links = [
                        (k, v)
                        for k, v in pdfs.items()
                        if v and str(v).startswith(UPLOADS_DIR)
                    ]
                    if links:
                        st.caption(
                            "📄 Docs adjuntos: " + " | ".join([k for k, _ in links])
                        )

    with tab_emp:
        empresas = ["— Seleccione —"] + sorted(
            df_g["Empresa"].str.strip().unique().tolist()
        )
        emp_sel = st.selectbox("Empresa:", empresas)
        if emp_sel != "— Seleccione —":
            sub = df_g[df_g["Empresa"].str.strip() == emp_sel]
            st.markdown(f"#### Personal de: **{emp_sel}** ({len(sub)} registros)")
            hoy = pd.Timestamp(date.today())
            for _, fila in sub.iterrows():
                ok, _ = evaluar(fila)
                cad = fila.get("Fecha_Caducidad")
                cad_str = str(pd.Timestamp(cad).date()) if pd.notna(cad) else "—"
                badge = (
                    "<span class='bok'>✅</span>"
                    if ok
                    else "<span class='bno'>🚫</span>"
                )
                r = st.columns([3, 2, 2, 2, 1])
                r[0].write(str(fila["Nombre"]))
                r[1].write(str(fila["Cedula"]))
                r[2].write(str(fila.get("Horario", "—")) or "—")
                r[3].write(cad_str)
                r[4].markdown(badge, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════════
# GESTIÓN DE APROBACIONES
# ════════════════════════════════════════════════════════════════════════════════
elif modulo == "✅ Gestión de Aprobaciones":
    rol_actual = st.session_state.rol
    titulo_rol = (
        "🦺 Seguridad Industrial"
        if rol_actual == "Seguridad Industrial"
        else "⚙️ Supervisor Planta"
    )
    st.markdown(
        f"""<div class='ph'><h1>✅ Gestión de Aprobaciones</h1>
    <p>Perfil: <b>{titulo_rol}</b> · Apruebe las solicitudes de ingreso de contratistas</p></div>""",
        unsafe_allow_html=True,
    )

    nuevos = st.session_state.nuevos_contratistas
    tab_ap, tab_docs = st.tabs(["📋 Solicitudes Pendientes", "📄 Documentos Adjuntos"])

    with tab_ap:
        if nuevos.empty:
            st.info(
                "Sin solicitudes nuevas. Los registros históricos de Google Sheets están aprobados."
            )
        else:
            for idx, fila in nuevos.iterrows():
                ok, motivos = evaluar(fila)
                nombre = str(fila["Nombre"])
                empresa = str(fila["Empresa"])
                cedula = str(fila["Cedula"])
                sol = str(fila.get("Solicitante", "—"))
                sol_si = str(fila.get("Supervisor_SI", "—"))
                horario = str(fila.get("Horario", "—"))
                ap_p = bool(fila.get("Aprobado_Planta", False))
                ap_s = bool(fila.get("Aprobado_SST", False))
                ambos_ap = ap_p and ap_s

                with st.container(border=True):
                    ca, cb = st.columns([5, 2])
                    ca.markdown(f"**{nombre}** — {empresa}")
                    ca.caption(
                        f"🆔 {cedula} · ⏰ {horario} · "
                        f"👔 Planta: {sol} · 🦺 Seg. Ind.: {sol_si}"
                    )

                    if ambos_ap:
                        cb.markdown(
                            "<span class='bok'>✅ HABILITADO</span>",
                            unsafe_allow_html=True,
                        )
                    elif ap_p and not ap_s:
                        cb.markdown(
                            "<span style='background:#f59e0b;color:#fff;padding:2px 8px;border-radius:4px;font-size:.78rem'>⏳ Pend. Seg. Ind.</span>",
                            unsafe_allow_html=True,
                        )
                    elif ap_s and not ap_p:
                        cb.markdown(
                            "<span style='background:#f59e0b;color:#fff;padding:2px 8px;border-radius:4px;font-size:.78rem'>⏳ Pend. Planta</span>",
                            unsafe_allow_html=True,
                        )
                    else:
                        cb.markdown(
                            "<span class='bno'>PENDIENTE</span>", unsafe_allow_html=True
                        )

                    # ── Botón según rol ──────────────────────────────────────
                    if rol_actual == "Supervisor Planta":
                        c1, c2 = st.columns([3, 2])
                        nuevo_p = c1.checkbox(
                            "✅ Aprobación Contratista (Planta)",
                            value=ap_p,
                            key=f"ap_{idx}",
                        )
                        if c2.button(
                            "💾 Guardar aprobación", key=f"sv_{idx}", type="primary"
                        ):
                            st.session_state.nuevos_contratistas.at[
                                idx, "Aprobado_Planta"
                            ] = nuevo_p
                            st.success(f"✅ Aprobación Planta guardada: {nombre}")
                            st.rerun()

                    elif rol_actual == "Seguridad Industrial":
                        c1, c2 = st.columns([3, 2])
                        nuevo_s = c1.checkbox(
                            "🦺 Aprobación Contratista (Seg. Industrial)",
                            value=ap_s,
                            key=f"as_{idx}",
                        )
                        if c2.button(
                            "💾 Guardar aprobación", key=f"sv_{idx}", type="primary"
                        ):
                            st.session_state.nuevos_contratistas.at[
                                idx, "Aprobado_SST"
                            ] = nuevo_s
                            st.success(
                                f"✅ Aprobación Seg. Industrial guardada: {nombre}"
                            )
                            st.rerun()

                    if ambos_ap:
                        st.success(
                            "🟢 Este trabajador está HABILITADO para ingresar a planta."
                        )

    with tab_docs:
        if nuevos.empty:
            st.info("Sin solicitudes nuevas.")
        else:
            for _, fila in nuevos.iterrows():
                nombre = str(fila["Nombre"])
                empresa = str(fila["Empresa"])
                ap_p = bool(fila.get("Aprobado_Planta", False))
                ap_s = bool(fila.get("Aprobado_SST", False))
                with st.expander(f"📋 {nombre} — {empresa}"):
                    d1, d2, d3, d4 = st.columns(4)
                    docs = {
                        "📌 IESS": (
                            fila.get("PDF_IESS", ""),
                            fila.get("Caducidad_IESS", ""),
                        ),
                        "🏥 Salud": (
                            fila.get("PDF_Salud", ""),
                            fila.get("Caducidad_Salud", ""),
                        ),
                        "⚠️ Riesgos": (
                            fila.get("PDF_Riesgos", ""),
                            fila.get("Caducidad_Riesgos", ""),
                        ),
                        "🪪 Cédula ID": (
                            fila.get("PDF_CedulaID", ""),
                            fila.get("Caducidad_Cedula", ""),
                        ),
                    }
                    for col_st, (label, (ruta, cad)) in zip(
                        [d1, d2, d3, d4], docs.items()
                    ):
                        col_st.markdown(f"**{label}**")
                        if ruta:
                            if ruta.startswith("http"):
                                col_st.markdown(f"[📄 Ver en Drive]({ruta})")
                            else:
                                col_st.markdown("📄 Guardado localmente")
                            col_st.markdown(estado_fecha(cad), unsafe_allow_html=True)
                        else:
                            col_st.markdown(
                                "<span class='bno'>Sin doc</span>",
                                unsafe_allow_html=True,
                            )
                    st.caption(
                        f"Estado: {'✅ Planta' if ap_p else '⏳ Planta pendiente'} · "
                        f"{'✅ Seg. Industrial' if ap_s else '⏳ Seg. Industrial pendiente'}"
                    )

# ════════════════════════════════════════════════════════════════════════════════
# REGISTRO DE ACCESOS
# ════════════════════════════════════════════════════════════════════════════════
elif modulo == "📊 Registro de Accesos":
    st.markdown(
        """<div class='ph'><h1>📊 Registro de Accesos</h1>
    <p>Historial de verificaciones realizadas en garita · Auditoría del sistema</p></div>""",
        unsafe_allow_html=True,
    )

    tab_log, tab_db = st.tabs(["📋 Log de Garita", "🗄️ Base de Datos Completa"])

    with tab_log:
        log = st.session_state.log_accesos
        if log.empty:
            st.info(
                "ℹ️ Sin registros. Las verificaciones en garita aparecen aquí automáticamente."
            )
        else:
            m1, m2, m3 = st.columns(3)
            m1.metric("Total consultas", len(log))
            m2.metric("✅ Permitidos", len(log[log["Resultado"] == "PERMITIDO"]))
            m3.metric("🚫 Denegados", len(log[log["Resultado"] == "DENEGADO"]))
            filtro = st.selectbox("Filtrar:", ["Todos", "PERMITIDO", "DENEGADO"])
            df_log = log if filtro == "Todos" else log[log["Resultado"] == filtro]
            st.dataframe(
                df_log.sort_values("Timestamp", ascending=False),
                use_container_width=True,
                hide_index=True,
            )
            csv = df_log.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Descargar log CSV", csv, "log_accesos.csv", "text/csv"
            )

    with tab_db:
        st.markdown("#### Base de datos completa (Google Sheets + solicitudes)")
        with st.spinner("Cargando..."):
            df_full = get_db_completa()
        hoy = pd.Timestamp(date.today())
        df_full["_cad"] = pd.to_datetime(df_full["Fecha_Caducidad"], errors="coerce")
        f1, f2 = st.columns(2)
        fe = f1.selectbox(
            "Empresa:",
            ["Todas"] + sorted(df_full["Empresa"].dropna().unique().tolist()),
        )
        fs = f2.selectbox("Estado:", ["Todos", "Vigente", "Caducada"])
        df_s = df_full.copy()
        if fe != "Todas":
            df_s = df_s[df_s["Empresa"].str.strip() == fe]
        if fs == "Vigente":
            df_s = df_s[df_s["_cad"] >= hoy]
        elif fs == "Caducada":
            df_s = df_s[df_s["_cad"] < hoy]
        cols_v = [
            "Empresa",
            "Nombre",
            "Cedula",
            "Fecha_Induccion",
            "Fecha_Caducidad",
            "Fuente",
        ]
        st.dataframe(
            df_s[cols_v].reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(f"Mostrando {len(df_s):,} de {len(df_full):,} registros")
        csv2 = df_s[cols_v].to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Descargar CSV", csv2, "contratistas.csv", "text/csv")
