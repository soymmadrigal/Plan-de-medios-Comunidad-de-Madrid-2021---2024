
# =========================================================
# Plan de Medios · Comunidad de Madrid
# App pública de consulta y análisis (versión endurecida)
# Creado por Mmadrigal
# Twitter/X: @Soymmadrigal
# Bluesky: mmadrigal.bsky.social
# =========================================================

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
import tempfile

st.set_page_config(page_title="Plan de Medios · Comunidad de Madrid", page_icon="📊", layout="wide")

BASE_URL = "https://www.comunidad.madrid/transparencia/sites/default/files/open-data/downloads"

def enlace_zip(periodo):
    return f"{BASE_URL}/planes_de_medios_{int(periodo)}_excel.zip"

def euros(x):
    try:
        return f"{int(round(x)):,}".replace(",", ".") + " €"
    except Exception:
        return "0 €"

@st.cache_data(show_spinner="Cargando datos públicos…")
def cargar_datos():
    df = pd.read_csv("Plan_consolidado.csv", sep=";", encoding="utf-8-sig")
    df["Importe"] = (
        df["Importe"].astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    df["Importe"] = pd.to_numeric(df["Importe"], errors="coerce").fillna(0)
    df["Periodo"] = pd.to_numeric(df["Periodo"], errors="coerce")
    return df[df["Periodo"].between(2021, 2024)]

@st.cache_data
def resumen_por_tipo(df):
    return df.groupby("Tipo")["Importe"].sum()

@st.cache_data
def ranking_soportes(df, n=15):
    return df.groupby("Soporte")["Importe"].sum().sort_values(ascending=False).head(n)

@st.cache_data
def evolucion_periodo(df):
    return df.groupby("Periodo")["Importe"].sum()

@st.cache_data
def grafico_pie(inv_tipo):
    return px.pie(inv_tipo, values=inv_tipo.values, names=inv_tipo.index, hole=0.4)

@st.cache_data
def grafico_ranking(ranking):
    fig = go.Figure(go.Bar(x=ranking.values, y=ranking.index, orientation="h"))
    fig.update_xaxes(tickformat=",", separatethousands=True)
    fig.update_layout(yaxis=dict(autorange="reversed"))
    return fig

@st.cache_data
def grafico_evolucion(evol):
    fig = px.line(x=evol.index, y=evol.values, markers=True)
    fig.update_yaxes(tickformat=",", separatethousands=True)
    return fig

def exportar_pdf(titulo, filtros, metricas, figuras):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph(titulo, styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<b>Filtros activos:</b> {filtros}", styles["Normal"]))
    story.append(Spacer(1, 12))
    tabla = [["Métrica", "Valor"]] + [[k, v] for k, v in metricas.items()]
    story.append(Table(tabla))
    story.append(Spacer(1, 16))
    for fig in figuras:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            fig.write_image(tmp.name, scale=2)
            story.append(Image(tmp.name, width=16*cm, height=9*cm))
            story.append(Spacer(1, 16))
    doc.build(story)
    buffer.seek(0)
    return buffer

def main():
    st.title("📊 Plan de Medios · Comunidad de Madrid")
    st.caption("Consulta interactiva del gasto en medios (2021–2024)")
    st.info("📈 Alta demanda en este momento. La aplicación mantiene todas las funciones, pero puede responder con más lentitud.")

    df = cargar_datos()

    st.sidebar.header("🔍 Consulta")
    periodo = st.sidebar.selectbox("Periodo", ["Todos"] + sorted(df["Periodo"].unique()))
    tipo = st.sidebar.selectbox("Tipo de medio", ["Todos"] + sorted(df["Tipo"].unique()))
    soporte = st.sidebar.selectbox("Soporte", ["Todos"] + sorted(df["Soporte"].unique()))
    vista = st.sidebar.radio("Vista", ["Resumen", "Evolución", "Datos"])
    high_load = st.sidebar.checkbox("Modo alto tráfico (recomendado)", value=True)

    df_f = df.copy()
    if periodo != "Todos":
        df_f = df_f[df_f["Periodo"] == periodo]
    if tipo != "Todos":
        df_f = df_f[df_f["Tipo"] == tipo]
    if soporte != "Todos":
        df_f = df_f[df_f["Soporte"] == soporte]

    if df_f.empty:
        st.warning("No hay datos para esta combinación.")
        st.stop()

    filtros_txt = f"Periodo={periodo}, Tipo={tipo}, Soporte={soporte}"

    metricas = {
        "Registros": f"{len(df_f):,}",
        "Inversión total": euros(df_f["Importe"].sum()),
        "Soportes únicos": f"{df_f['Soporte'].nunique()}"
    }

    c1, c2, c3 = st.columns(3)
    for col, (k, v) in zip([c1, c2, c3], metricas.items()):
        col.metric(k, v)

    figuras_pdf = []

    if vista == "Resumen":
        inv_tipo = resumen_por_tipo(df_f)
        fig1 = grafico_pie(inv_tipo)
        figuras_pdf.append(fig1)
        st.plotly_chart(fig1, width="stretch")
        if not high_load:
            ranking = ranking_soportes(df_f)
            fig2 = grafico_ranking(ranking)
            figuras_pdf.append(fig2)
            st.plotly_chart(fig2, width="stretch")

    elif vista == "Evolución":
        evol = evolucion_periodo(df_f)
        fig = grafico_evolucion(evol)
        figuras_pdf.append(fig)
        st.plotly_chart(fig, width="stretch")

    elif vista == "Datos":
        df_show = df_f.copy()
        df_show["Importe"] = df_show["Importe"].apply(euros)
        st.dataframe(df_show[["Periodo", "Tipo", "Soporte", "Importe", "Origen"]], width="stretch")

    st.markdown("---")
    if st.button("Generar informe PDF"):
        if len(df_f) > 3000:
            st.warning("El informe PDF solo se genera para selecciones más acotadas (por rendimiento).")
        else:
            pdf = exportar_pdf("Consulta Plan de Medios – Comunidad de Madrid", filtros_txt, metricas, figuras_pdf)
            st.download_button("📄 Descargar informe PDF", pdf, file_name="consulta_plan_medios.pdf", mime="application/pdf")

    with st.expander("📦 Fuentes oficiales"):
        for p in sorted(df_f["Periodo"].unique()):
            st.markdown(f"- {p}: [{enlace_zip(p)}]({enlace_zip(p)})")

    st.markdown("Creado por **Mmadrigal** · [@Soymmadrigal](https://twitter.com/Soymmadrigal) · [mmadrigal.bsky.social](https://bsky.app/profile/mmadrigal.bsky.social)")

if __name__ == "__main__":
    main()
