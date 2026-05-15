# Configuración Snowflake — Reporte Ejecutivo RDA
## PMO Hub · CEN Systems

---

## 1. Credenciales de conexión

| Parámetro | Valor |
|-----------|-------|
| **Account** | `a4736573681671-censystemsdb` |
| **User** | `rda_dashboard` |
| **Password** | `RdaDashboard2024` |
| **Role** | `PM` |
| **Warehouse** | `COMPUTE_WH` |

> Las credenciales viven como **GitHub Secrets** en `maxceca/pmo-hub`:
> Settings → Secrets and variables → Actions

---

## 2. Estructura de datos

| Parámetro | Valor |
|-----------|-------|
| **Database** | `MUAMBA_EXTRACT` |
| **Schema** | `MUAMBA_API` |
| **Tabla USD** | `MUAMBA_RDA_USD` |
| **Tabla MXN** | `MUAMBA_RDA_MXN` |
| **Filtro de fecha** | `WHERE LOAD_DATE = (SELECT MAX(LOAD_DATE) FROM tabla)` |
| **Filtro de año** | Solo proyectos desde `2023` en adelante (campo derivado del número de PRY) |

---

## 3. Columnas utilizadas

### Identificación y clasificación

| Columna Snowflake | Campo en dashboard |
|-------------------|--------------------|
| `PROYECTO` | Número de proyecto (clave única) |
| `NOMBRE` | Nombre del proyecto |
| `ESTATUS` | Estatus (Activo / Cerrado / etc.) |
| `SUCURSAL` | Sucursal |
| `NOMBRE_CLIENTE` | Cliente |
| `UNIDAD_NEGOCIO` | Unidad de negocio |
| `TIPO_VENTA` | Tipo de venta |
| `PORTAFOLIO` | Portafolio |
| `PM` | Project Manager |
| `AM` | Account Manager |
| `INGENIERO_PREVENTA` | Ingeniero preventa |

### Fechas y facturación

| Columna Snowflake | Campo en dashboard |
|-------------------|--------------------|
| `FECHA_CREACION` | Fecha de creación |
| `FECHA_INICIO` | Fecha inicio |
| `FECHA_FIN` | Fecha fin |
| `FECHA_ULTIMA_FACTURA` | Última factura |
| `SIGUIENTE_FACTURACION` | Siguiente facturación |
| `MONTO_A_FACTURAR` | Monto a facturar |
| `VENTA_PREVISTA_TOTAL` | Venta Prevista (KPI principal) |
| `FACTURADO_CON_NC` | Facturado con NC (KPI principal) |

### Costos Previstos

| Columna Snowflake | Rubro en dashboard |
|-------------------|--------------------|
| `COSTO_PREVISTO_EQUIPO` | Equipo — Previsto |
| `COSTO_PREVISTO_SERVICIOS` | Servicios — Previsto |
| `COSTO_PREVISTO_MOI` | MOI — Previsto |
| `COSTO_PREVISTO_MOD` | MOD — Previsto |
| `COSTO_PREVISTO_GASTOS` | Gastos — Previsto |
| `COSTO_PREVISTO_OTROS` | Otros — Previsto |
| `COSTO_PREVISTO_TOTAL` | Total Costo Previsto |

### Costos Reales

| Columna Snowflake | Rubro en dashboard | Nota |
|-------------------|--------------------|------|
| `COSTO_REAL_EQUIPO_ENTREGADO` | Equipo — Real | ⚠️ Usar ENTREGADO, no FACTURADO |
| `COSTO_REAL_SERVICIOS` | Servicios — Real | |
| `COSTO_REAL_MOI` | MOI — Real | |
| `COSTO_REAL_MOD` | MOD — Real | |
| `COSTO_REAL_GASTOS` | Gastos — Real | |
| `COSTOS_REAL_OTROS` | Otros — Real | ⚠️ Nombre en plural: COSTOS (no COSTO) |
| `COSTO_REAL_TOTAL` | Total Costo Real | |
| `MARGEN_PREVISTO` | Margen previsto | |

---

## 4. Notas importantes

- **`COSTOS_REAL_OTROS`** lleva "COSTOS" en plural — es diferente a todas las demás columnas que usan "COSTO" en singular. No cambiar.
- **`COSTO_REAL_EQUIPO_ENTREGADO`** reemplazó a `COSTO_REAL_EQUIPO_FACTURADO` por decisión del equipo.
- El año del proyecto se deriva del número de PRY: `PRY-260401-06360` → año `2026`.
- La moneda (USD/MXN) se asigna según la tabla de origen, no viene como columna.
- El dashboard solo muestra proyectos desde el año **2023** en adelante.

---

## 5. Automatización

| Parámetro | Valor |
|-----------|-------|
| **Workflow** | `.github/workflows/update-rda.yml` |
| **Horario** | Todos los días a las **10:00 AM CDMX** (16:00 UTC) |
| **Script** | `rda/generate_rda.py` |
| **Salida** | `rda/index.html` (se sobreescribe con datos frescos) |
| **Ejecución manual** | GitHub → Actions → Actualizar Dashboard RDA → Run workflow |

---

## 6. Cómo verificar que los datos están al día

```python
# Ejecutar con Python + snowflake-connector-python instalado
import snowflake.connector
conn = snowflake.connector.connect(
    account="a4736573681671-censystemsdb",
    user="rda_dashboard",
    password="RdaDashboard2024",
    warehouse="COMPUTE_WH",
    database="MUAMBA_EXTRACT",
    schema="MUAMBA_API",
    role="PM",
)
cur = conn.cursor()
for tabla in ["MUAMBA_RDA_USD", "MUAMBA_RDA_MXN"]:
    cur.execute(f"SELECT MAX(LOAD_DATE), COUNT(*) FROM MUAMBA_EXTRACT.MUAMBA_API.{tabla}")
    r = cur.fetchone()
    print(f"{tabla}: ultimo LOAD_DATE = {r[0]}, filas = {r[1]:,}")
conn.close()
```

---

## 7. URL del dashboard

**https://maxceca.github.io/pmo-hub/rda/**
