
# =========================================================
# Plan de Medios · Comunidad de Madrid
# App pública de consulta y análisis
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

# -------------------------------------------------
# CONFIGURACIÓN GENERAL
# -------------------------------------------------
st.set_page_config(
    page_title="Plan de Medios · Comunidad de Madrid",
    page_icon="📊",
    layout="wide"
)

BASE_URL = "https://www.comunidad.madrid/transparencia/sites/default/files/open-data/downloads"

def enlace_zip(periodo):
    return f"{BASE_URL}/planes_de_medios_{int(periodo)}_excel.zip"

def euros(x):
    return f"{int(round(x)):,}".replace(",", ".") + " €"

# -------------------------------------------------
# CARGA DE DATOS
# -------------------------------------------------
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

# -------------------------------------------------
# PDF
# -------------------------------------------------
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

# -------------------------------------------------
# APP
# -------------------------------------------------
def main():

    st.title("📊 Plan de Medios · Comunidad de Madrid")
    st.caption("Consulta interactiva del gasto en medios (2021–2024)")

    df = cargar_datos()

    # ---------------- SIDEBAR ----------------
    st.sidebar.header("🔍 Consulta")

    periodo = st.sidebar.selectbox("Periodo", ["Todos"] + sorted(df["Periodo"].unique()))
    tipo = st.sidebar.selectbox("Tipo de medio", ["Todos"] + sorted(df["Tipo"].unique()))
    soporte = st.sidebar.selectbox("Soporte", ["Todos"] + sorted(df["Soporte"].unique()))

    vista = st.sidebar.radio(
        "Vista",
        ["Resumen", "Evolución", "Datos"]
    )

    st.sidebar.markdown("---")
    modo_periodista = st.sidebar.checkbox("📰 Modo periodista (consultas rápidas)")

    # ---------------- FILTROS ----------------
    df_f = df.copy()
    if periodo != "Todos":
        df_f = df_f[df_f["Periodo"] == periodo]
    if tipo != "Todos":
        df_f = df_f[df_f["Tipo"] == tipo]
    if soporte != "Todos":
        df_f = df_f[df_f["Soporte"] == soporte]

    filtros_txt = f"Periodo={periodo}, Tipo={tipo}, Soporte={soporte}"

    if df_f.empty:
        st.warning("No hay datos para esta combinación.")
        st.stop()

    # ======================================================
    # MODO PERIODISTA
    # ======================================================
    if modo_periodista:
        st.subheader("📰 Consulta rápida para medios")

        soporte_prensa = st.selectbox(
            "Selecciona un medio",
            sorted(df["Soporte"].unique())
        )

        df_m = df[df["Soporte"] == soporte_prensa]
        if periodo != "Todos":
            df_m = df_m[df_m["Periodo"] == periodo]

        total_medio = df_m["Importe"].sum()
        total_global = df["Importe"].sum()
        tipo_medio = df_m["Tipo"].iloc[0]

        ranking = (
            df.groupby("Soporte")["Importe"]
            .sum()
            .sort_values(ascending=False)
        )
        posicion = ranking.index.get_loc(soporte_prensa) + 1

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Inversión total", euros(total_medio))
        c2.metric("📊 % del total", f"{total_medio / total_global * 100:.2f}%")
        c3.metric("🏷️ Tipo de medio", tipo_medio)
        c4.metric("📈 Ranking", f"#{posicion}")

        evol = df_m.groupby("Periodo")["Importe"].sum().reset_index()
        fig = px.line(
            evol,
            x="Periodo",
            y="Importe",
            markers=True,
            labels={"Importe": "€"},
        )
        fig.update_yaxes(tickformat=",", separatethousands=True)
        st.plotly_chart(fig, width="stretch")

        st.code(
            f"Entre 2021 y 2024, la Comunidad de Madrid destinó "
            f"{euros(total_medio)} en publicidad institucional a {soporte_prensa}.",
            language="text"
        )

        with st.expander("📋 Ver datos del medio"):
            df_show = df_m.copy()
            df_show["Importe"] = df_show["Importe"].apply(euros)
            st.dataframe(
                df_show[["Periodo", "Importe", "Origen"]]
                .sort_values("Periodo", ascending=False),
                width="stretch"
            )

        st.stop()

    # ---------------- MÉTRICAS GENERALES ----------------
    metricas = {
        "Registros": f"{len(df_f):,}",
        "Inversión total": euros(df_f["Importe"].sum()),
        "Soportes únicos": f"{df_f['Soporte'].nunique()}"
    }

    c1, c2, c3 = st.columns(3)
    for col, (k, v) in zip([c1, c2, c3], metricas.items()):
        col.metric(k, v)

    figuras_pdf = []

    # ---------------- VISTAS ----------------
    if vista == "Resumen":
        inv_tipo = df_f.groupby("Tipo")["Importe"].sum()
        fig1 = px.pie(
            inv_tipo,
            values=inv_tipo.values,
            names=inv_tipo.index,
            hole=0.4
        )
        figuras_pdf.append(fig1)
        st.plotly_chart(fig1, width="stretch")

        ranking = (
            df_f.groupby("Soporte")["Importe"]
            .sum()
            .sort_values(ascending=False)
            .head(15)
        )
        fig2 = go.Figure(go.Bar(
            x=ranking.values,
            y=ranking.index,
            orientation="h"
        ))
        fig2.update_xaxes(tickformat=",", separatethousands=True)
        fig2.update_layout(yaxis=dict(autorange="reversed"))
        figuras_pdf.append(fig2)
        st.plotly_chart(fig2, width="stretch")

    elif vista == "Evolución":
        evol = df_f.groupby("Periodo")["Importe"].sum()
        fig = px.line(
            x=evol.index,
            y=evol.values,
            markers=True
        )
        fig.update_yaxes(tickformat=",", separatethousands=True)
        figuras_pdf.append(fig)
        st.plotly_chart(fig, width="stretch")

    elif vista == "Datos":
        df_show = df_f.copy()
        df_show["Importe"] = df_show["Importe"].apply(euros)
        st.dataframe(
            df_show[["Periodo", "Tipo", "Soporte", "Importe", "Origen"]]
            .sort_values(["Periodo", "Importe"], ascending=[False, False]),
            width="stretch"
        )

    # ---------------- DESCARGAS ----------------
    st.markdown("---")
    pdf = exportar_pdf(
        "Consulta Plan de Medios – Comunidad de Madrid",
        filtros_txt,
        metricas,
        figuras_pdf
    )

    st.download_button(
        "📄 Exportar informe PDF",
        pdf,
        file_name="consulta_plan_medios.pdf",
        mime="application/pdf"
    )

    with st.expander("📦 Fuentes oficiales"):
        for p in sorted(df_f["Periodo"].unique()):
            st.markdown(f"- {p}: [{enlace_zip(p)}]({enlace_zip(p)})")

    st.markdown(
        "Creado por **Mmadrigal** · "
        "[@Soymmadrigal](https://twitter.com/Soymmadrigal) · "
        "[mmadrigal.bsky.social](https://bsky.app/profile/mmadrigal.bsky.social)"
    )

if __name__ == "__main__":
    main()
