# Plan Comercial y Técnico — Sistema de Cubicación con IA
**Versión 1.0 — Mayo 2026**

---

## RESUMEN EJECUTIVO

**Producto:** Sistema de cubicación automática y presupuesto de materiales para proyectos de construcción, impulsado por IA (Claude API).

**Propuesta central:**
> "Tu cubicación lista en 4 horas. Tú la firmas, la IA la arma."

**Mercado objetivo:** Constructoras medianas, estudios de arquitectura e ingeniería en LATAM (Chile, Colombia, México, Perú) que licitan 5-20 proyectos por mes y no tienen cubicador de planta.

**Modelo de negocio:** Servicio gestionado en fase 1 → SaaS en fase 2 → White label corporativo en fase 3.

**Proyección año 1:** $30,000 - $60,000 USD de ingresos con margen del 75-85%.

**Inversión inicial requerida:** $500 - $3,000 USD (sin necesidad de equipo externo usando Claude Code).

---

---

# PARTE I — PLAN COMERCIAL

---

## 1. ANÁLISIS DE MERCADO

### 1.1 Tamaño del mercado

| País | Empresas constructoras activas | Estudios de arquitectura | Proyectos/año estimados |
|------|-------------------------------|--------------------------|------------------------|
| Chile | 8,000+ | 4,500+ | 120,000+ |
| Colombia | 22,000+ | 8,000+ | 280,000+ |
| México | 85,000+ | 25,000+ | 800,000+ |
| Perú | 18,000+ | 5,000+ | 150,000+ |
| **Total** | **133,000+** | **42,500+** | **1,350,000+** |

**Mercado addressable inicial (Chile + Colombia):** 30,000 empresas potenciales.
**Segmento objetivo realista (constructoras medianas):** 8,000 empresas.
**Penetración meta año 1:** 0.5% = 40 clientes.

### 1.2 Dolor del mercado

```
Situación actual sin el producto:
→ Cubicación manual: 2-5 días por proyecto
→ Costo profesional cubicador: $500-2,000 USD/proyecto
→ Error humano promedio: 5-10%
→ Pérdida de licitaciones por no entregar a tiempo: frecuente
→ Escasez de cubicadores especializados: crítica en regiones

Consecuencia económica del problema:
→ Una constructora que pierde 3 licitaciones/año por plazo
  pierde potencialmente $50,000-500,000 USD en contratos
```

### 1.3 Competencia actual

| Competidor | Fortaleza | Debilidad | Precio aprox. |
|-----------|-----------|-----------|---------------|
| Civils.ai | Muy preciso en obra civil | Solo inglés, sin precios LATAM | $200-800/mes |
| Beam AI | QA humano incluido | Solo inglés, costoso | $300-1,000/mes |
| Togal.AI | Rápido en plantas | El estimador completa manualmente | $199-599/mes |
| Kreo | Integración BIM buena | Solo inglés, complejo | $400+/mes |
| metroKUBIKO | En español, Colombia | Sin lectura de planos PDF con IA | $50-200/mes |
| Budquo | Bueno para presupuesto | Sin extracción de medidas de planos | $80-300/mes |

**Gap de mercado claro:** No existe una herramienta en español que combine lectura de planos PDF/DWG + cubicación automática + precios locales LATAM en un solo flujo.

### 1.4 Perfil del cliente ideal

**Empresa:** Constructora mediana o estudio de arquitectura/ingeniería.

**Características:**
- 5-50 empleados
- 5-20 licitaciones activas por mes
- No tiene cubicador de planta dedicado
- El arquitecto o jefe de obra hace la cubicación manualmente
- Trabaja con planos en PDF, DWG o Revit
- Opera en Chile, Colombia, México o Perú

**Dolor específico:**
- Pierde licitaciones porque no alcanza a preparar el presupuesto
- El proceso manual toma 3-5 días y es propenso a errores
- No puede permitirse contratar un cubicador full-time

---

## 2. PROPUESTA DE VALOR

### 2.1 Para el cliente

```
ANTES (sin el producto):
→ 3-5 días para cubicar un proyecto mediano
→ $500-2,000 USD en honorarios de cubicador externo
→ Riesgo de error del 5-10%
→ Estrés por plazos de licitación

DESPUÉS (con el producto):
→ Mediciones listas en 4-8 horas
→ Costo: $50-250 USD por proyecto
→ El profesional valida y firma (confianza)
→ Capacidad de licitar 3x más proyectos
```

### 2.2 Posicionamiento

**Lo que NO somos:**
- ❌ Un sistema que reemplaza al cubicador
- ❌ Precisión perfecta sin revisión humana
- ❌ Una caja negra que nadie entiende

**Lo que SÍ somos:**
- ✅ El copiloto que hace el 75% del trabajo pesado
- ✅ La herramienta que libera al profesional para pensar, no para medir
- ✅ Transparente: siempre sabes cómo llegó a cada número
- ✅ Hecho para LATAM: precios locales, normativa local, soporte en español

### 2.3 Mensaje central por segmento

| Segmento | Mensaje |
|----------|---------|
| Constructora mediana | "Licita el doble de proyectos sin contratar más gente" |
| Estudio de arquitectura | "De plano a presupuesto en una mañana" |
| Jefe de obra independiente | "Tu cubicación profesional en horas, no en días" |
| Empresa de ingeniería | "Reduce el error humano en presupuestos al mínimo" |

---

## 3. MODELO DE NEGOCIO

### 3.1 Tres etapas de evolución

```
ETAPA 1 (mes 1-4): SERVICIO GESTIONADO
El cliente envía los planos → nosotros procesamos → entregamos Excel
Sin software que el cliente instale. Tú operás el sistema.
Precio: $150-400 USD por proyecto

ETAPA 2 (mes 5-12): SAAS SELF-SERVICE
El cliente accede a la plataforma web y procesa sus propios planos.
Precio: suscripción mensual por volumen

ETAPA 3 (mes 13-24): WHITE LABEL / CORPORATIVO
Licencia del sistema para gremios, cámaras, empresas grandes.
Precio: contrato anual $20,000-80,000 USD
```

### 3.2 Estructura de precios (Etapa 2 — SaaS)

```
┌─────────────────┬──────────────┬────────────────┬──────────────┐
│ Plan            │ Precio/mes   │ Proyectos/mes  │ Incluye      │
├─────────────────┼──────────────┼────────────────┼──────────────┤
│ Starter         │ $79 USD      │ 8 proyectos    │ PDF/DWG      │
│ Profesional     │ $179 USD     │ 25 proyectos   │ + IFC/Revit  │
│ Empresa         │ $399 USD     │ 60 proyectos   │ + API access │
│ Corporativo     │ Cotización   │ Ilimitado      │ White label  │
└─────────────────┴──────────────┴────────────────┴──────────────┘

Proyecto adicional fuera del plan: $12 USD c/u
Trial gratuito: 1 proyecto completo sin tarjeta de crédito
```

### 3.3 Economía unitaria

```
COSTO POR PROYECTO (variable):
→ Claude API:          $0.50 - $3.00 USD
→ Storage temporal:    $0.05 USD
→ Procesamiento:       $0.10 USD
→ TOTAL COSTO:         $0.65 - $3.15 USD

PRECIO COBRADO:
→ Servicio gestionado: $200 - $400 USD
→ SaaS (por proyecto): $3.20 - $7.20 USD (implícito en plan)

MARGEN BRUTO:          75 - 98%
```

---

## 4. ESTRATEGIA GO-TO-MARKET

### 4.1 Fases de lanzamiento

#### FASE 0 — Validación (semanas 1-4, $0 inversión)
```
Objetivo: confirmar que el mercado paga por esto

Acciones:
→ Contactar 10 constructoras/estudios conocidos
→ Ofrecer 5 cubicaciones gratuitas a cambio de feedback
→ Documentar resultados: tiempo ahorrado, errores, precisión
→ Conseguir 3 testimonios con nombre y empresa
→ Definir qué tipos de plano funcionan mejor

Criterio de éxito: 3 empresas dicen "pagaría por esto"
```

#### FASE 1 — Tracción inicial (mes 1-3, $0-200/mes)
```
Objetivo: 10 clientes de pago, $2,000 USD/mes

Canales:
→ Red personal y referidos directos
→ WhatsApp de grupos profesionales (arquitectos, ingenieros)
→ LinkedIn orgánico: 3 posts/semana con resultados reales
→ 1 charla gratuita en colegio profesional o cámara de construcción

Conversión esperada:
→ 10 empresas contactadas → 4 pruebas gratis → 2 clientes pago
→ Ciclo de venta: 2-4 semanas
```

#### FASE 2 — Crecimiento (mes 4-9, $300-600/mes)
```
Objetivo: 40 clientes, $6,000-8,000 USD/mes

Canales adicionales:
→ YouTube: 2 videos/mes con demos reales
→ Google Ads: keywords de cubicación en español ($200/mes)
→ LinkedIn Ads: gerentes de constructoras ($150/mes)
→ Alianzas con proveedores de materiales (distribuidores)
→ Programa de referidos: 1 mes gratis por cada cliente referido

SEO: artículos sobre cubicación con IA en español
```

#### FASE 3 — Escala (mes 10-24, $800-1,500/mes)
```
Objetivo: 100+ clientes, $15,000-25,000 USD/mes

Canales:
→ Cámaras de construcción: presentaciones y membresías
→ Universidades: convenio con facultades de arquitectura/ingeniería
→ Integraciones con software de obra (Procore, BuilderTrend)
→ Revendedores en otros países LATAM
→ 1 cliente corporativo white label
```

### 4.2 Embudo de ventas

```
TRÁFICO
(LinkedIn, YouTube, referidos, Google)
        ↓
LEAD (interesado)
→ Descarga guía gratuita "Cubicación con IA: guía práctica"
→ Suscripción a newsletter semanal con tips de presupuesto
        ↓
PRUEBA GRATUITA
→ Procesa 1 proyecto gratis, resultado en 24 horas
→ Email de seguimiento con métricas del resultado
        ↓
CONVERSIÓN
→ Oferta: "Tu siguiente proyecto al 50% si contratas este mes"
→ Llamada de onboarding de 30 minutos
        ↓
RETENCIÓN
→ Newsletter mensual con tips de cubicación
→ Soporte por WhatsApp
→ Actualización mensual de base de precios
        ↓
REFERIDO
→ "Trae a un colega y obtén 1 mes gratis"
```

### 4.3 Contenido que convierte (calendario)

```
SEMANA 1: Video YouTube — "Cubiqué 500 m2 en 40 minutos con IA"
SEMANA 2: Post LinkedIn — Caso de cliente real con números
SEMANA 3: Artículo blog — "5 errores en cubicación manual que cuestan millones"
SEMANA 4: Video YouTube — "Las limitaciones reales de la IA en cubicación"

Repetir con variaciones. El contenido honesto genera más confianza
que el contenido perfecto.
```

---

## 5. PROYECCIONES FINANCIERAS

### 5.1 Escenario conservador

```
         Clientes  Ingreso/mes  Costos/mes  Utilidad/mes
Mes 1:      0        $0           $200         -$200
Mes 2:      2        $800         $250         +$550
Mes 3:      6        $1,800       $350         +$1,450
Mes 4:     12        $3,200       $600         +$2,600
Mes 6:     25        $5,500       $900         +$4,600
Mes 9:     45        $9,000       $1,500       +$7,500
Mes 12:    70        $14,000      $2,200       +$11,800
Mes 18:   110        $22,000      $3,500       +$18,500
Mes 24:   160        $32,000      $5,000       +$27,000

TOTAL AÑO 1: ~$45,000 USD utilidad neta
TOTAL AÑO 2: ~$220,000 USD utilidad neta
```

### 5.2 Desglose de costos operativos (mes 12)

```
Claude API (70 clientes × 20 proy × $1.50): $2,100
Hosting / infraestructura:                    $300
Herramientas SaaS (email, analytics, soporte): $180
Legal / contabilidad:                          $150
Marketing / publicidad:                        $600
Actualización base de precios (mensual):       $200
─────────────────────────────────────────────────
TOTAL:                                        $3,530
```

### 5.3 Hitos financieros

```
Break-even:             Mes 3-4 (6-12 clientes)
$10,000 USD/mes:        Mes 9-10
$20,000 USD/mes:        Mes 15-16
Primer cliente corp.:   Mes 14-18 (+$30,000 USD/año)
```

---

## 6. KPIs Y MÉTRICAS CLAVE

```
ADQUISICIÓN
→ CAC (Costo por cliente): meta < $120 USD
→ Tasa de conversión trial → pago: meta > 30%
→ Tiempo del ciclo de venta: meta < 3 semanas

PRODUCTO
→ Precisión de cubicación vs manual: meta > 90%
→ Tiempo de entrega por proyecto: meta < 8 horas
→ NPS (satisfacción): meta > 50

NEGOCIO
→ MRR (ingreso mensual recurrente): seguimiento semanal
→ Churn mensual: meta < 5%
→ LTV (valor de vida del cliente): meta > $1,800 USD
→ LTV/CAC ratio: meta > 15x
→ Margen bruto: meta > 75%
```

---

---

# PARTE II — PLAN TÉCNICO

---

## 7. ARQUITECTURA DEL SISTEMA

### 7.1 Diagrama de flujo completo

```
ENTRADA
────────────────────────────────────────────
│  PDF planos  │  DWG/DXF  │  IFC/Revit  │
────────────────────────────────────────────
                    ↓
CAPA DE INGESTA
────────────────────────────────────────────
│         Validación y normalización        │
│   (formato, resolución, páginas, escala)  │
────────────────────────────────────────────
                    ↓
        ┌───────────────────────┐
        │   ¿Qué tipo de        │
        │   archivo?            │
        └───────────────────────┘
          ↓           ↓           ↓
        PDF          DWG         IFC
          ↓           ↓           ↓
    Claude Vision   ezdxf     IfcOpenShell
    (extracción    (parseo    (extracción
     visual)       vectorial)  BIM directa)
          ↓           ↓           ↓
────────────────────────────────────────────
       NORMALIZACIÓN A JSON UNIFICADO
  {elementos: [{tipo, geometría, propiedades}]}
────────────────────────────────────────────
                    ↓
CAPA DE INTELIGENCIA (Claude API)
────────────────────────────────────────────
│  Clasificación de elementos               │
│  Cálculo de superficies y volúmenes       │
│  Aplicación de descuentos (vanos, etc.)   │
│  Asignación de partidas                   │
│  Validación de consistencia               │
────────────────────────────────────────────
                    ↓
CAPA DE PRECIOS
────────────────────────────────────────────
│  Base de precios unitarios por región     │
│  [PREOC / SINCO / SIPE / precios propios] │
│  APU automático (mat + MO + maquinaria)   │
────────────────────────────────────────────
                    ↓
SALIDA
────────────────────────────────────────────
│  Excel presupuesto  │  PDF informe  │ API │
────────────────────────────────────────────
```

### 7.2 Componentes principales

```
1. PROCESADOR DE ARCHIVOS
   → Recibe el archivo del cliente
   → Detecta formato y calidad
   → Extrae páginas relevantes
   → Normaliza resolución para Claude Vision

2. MOTOR DE EXTRACCIÓN
   → PDF:  pdfplumber + Claude Vision API
   → DWG:  ezdxf + clasificación por capas + Claude
   → IFC:  IfcOpenShell + extracción directa de propiedades

3. MOTOR DE CUBICACIÓN (Claude)
   → Recibe elementos normalizados
   → Aplica reglas de cubicación según normativa
   → Calcula m2, ml, m3, unidades
   → Genera tabla de cubicación

4. MOTOR DE PRESUPUESTO
   → Cruza cubicación con base de precios
   → Genera APU por partida
   → Calcula subtotales y totales
   → Aplica AIU (Administración, Imprevistos, Utilidad)

5. GENERADOR DE REPORTES
   → Excel formateado (openpyxl)
   → PDF profesional (reportlab)
   → JSON para integración con otros sistemas

6. INTERFAZ WEB (fase 2)
   → Upload de planos
   → Seguimiento en tiempo real del proceso
   → Revisión y edición de resultados
   → Historial de proyectos
```

---

## 8. STACK TECNOLÓGICO

### 8.1 Backend

```python
# Lenguaje principal
Python 3.12+

# IA y procesamiento
anthropic          # Claude API (Vision + text)
ezdxf              # Lectura DWG/DXF
ifcopenshell       # Lectura IFC/BIM
pdfplumber         # Extracción PDF
pymupdf            # Renderizado PDF a imagen
Pillow             # Procesamiento de imágenes

# Base de datos
PostgreSQL         # Proyectos, clientes, historial
SQLite             # Base de precios unitarios local
Redis              # Queue de procesamiento async

# Generación de reportes
openpyxl           # Excel formateado
reportlab          # PDF profesional
jinja2             # Templates de reportes

# API y web
FastAPI            # API REST
uvicorn            # Servidor ASGI
pydantic           # Validación de datos
```

### 8.2 Frontend (fase 2)

```javascript
// Framework
Next.js 15

// UI Components
Tailwind CSS
shadcn/ui

// Estado y fetching
React Query
Zustand

// Visualización de planos
PDF.js             // Visualizar PDF con anotaciones
Fabric.js          // Canvas interactivo para markups
```

### 8.3 Infraestructura

```yaml
# Fase 1 (servicio gestionado): mínimo
Servidor:    VPS $20-40/mes (DigitalOcean / Vultr)
Storage:     S3-compatible para planos ($5-10/mes)
Total:       $25-50/mes

# Fase 2 (SaaS): escalable
App server:  Railway o Render ($30-80/mes)
Database:    Supabase PostgreSQL ($25/mes)
Queue:       Upstash Redis ($10/mes)
Storage:     Cloudflare R2 ($10-30/mes)
CDN:         Cloudflare (gratis)
Total:       $75-145/mes

# Fase 3 (escala):
Migrar a AWS/GCP según demanda
```

---

## 9. FASES DE DESARROLLO

### FASE 0 — Prueba de concepto (semana 1-2)

**Objetivo:** Confirmar que Claude Vision puede extraer mediciones útiles de planos reales.

```python
# Script mínimo de validación
import anthropic
import base64
import json

def extraer_elementos_plano(ruta_pdf: str) -> dict:
    """
    Dado un PDF de plano arquitectónico,
    extrae elementos y mediciones básicas.
    """
    client = anthropic.Anthropic()
    
    # Convertir PDF a imagen
    imagen_base64 = pdf_a_imagen_base64(ruta_pdf)
    
    prompt = """
    Analiza este plano arquitectónico y extrae:
    
    1. RECINTOS: nombre, área estimada en m2
    2. MUROS: tipo (interior/exterior), longitud total por tipo
    3. VANOS: puertas (cantidad y tipo), ventanas (cantidad y tipo)
    4. ESCALA del plano si es visible
    
    Devuelve JSON con esta estructura exacta:
    {
      "escala": "1:50" o null,
      "recintos": [{"nombre": str, "area_m2": float}],
      "muros": [{"tipo": str, "longitud_ml": float}],
      "puertas": [{"tipo": str, "cantidad": int}],
      "ventanas": [{"tipo": str, "cantidad": int}],
      "observaciones": str
    }
    
    Si no puedes determinar un valor con confianza, usa null.
    """
    
    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": imagen_base64
                    }
                },
                {"type": "text", "text": prompt}
            ]
        }]
    )
    
    return json.loads(response.content[0].text)
```

**Entregable:** Script que procesa 5 planos de prueba y genera reporte de precisión.

---

### FASE 1 — MVP Servicio Gestionado (semanas 3-6)

**Objetivo:** Sistema funcional para procesar proyectos manualmente.

```
Módulos a desarrollar:
├── ingesta/
│   ├── pdf_processor.py      # PDF → imágenes normalizadas
│   ├── dwg_processor.py      # DWG → elementos con ezdxf
│   └── ifc_processor.py      # IFC → cantidades con ifcopenshell
│
├── extraccion/
│   ├── vision_extractor.py   # Claude Vision → elementos JSON
│   ├── element_classifier.py # Clasificar y validar elementos
│   └── normalizer.py         # Unificar formato de salida
│
├── cubicacion/
│   ├── calculator.py         # Cálculo de m2, ml, m3
│   ├── rules_engine.py       # Reglas por normativa (MINVU, NSR-10)
│   └── validator.py          # Detectar inconsistencias
│
├── presupuesto/
│   ├── price_database.py     # Base de precios por región
│   ├── apu_generator.py      # APU: materiales + MO + maquinaria
│   └── budget_assembler.py   # Ensamblar presupuesto final
│
├── reportes/
│   ├── excel_generator.py    # Excel formateado profesional
│   └── pdf_generator.py      # PDF para entrega al cliente
│
└── main.py                   # Orquestador del flujo completo
```

**Entregable:** CLI que toma un PDF/DWG como input y genera Excel de presupuesto.

```bash
python main.py --input plano.pdf --region chile --output presupuesto.xlsx
```

---

### FASE 2 — Plataforma Web SaaS (semanas 7-16)

**Objetivo:** Interfaz web donde el cliente sube sus planos y recibe resultados.

```
Funcionalidades MVP web:
├── Autenticación (registro, login, planes)
├── Upload de archivos (PDF, DWG, IFC)
├── Estado del procesamiento en tiempo real
├── Visualizador del plano con elementos marcados
├── Editor de cubicación (el profesional puede ajustar)
├── Generador de reportes (Excel / PDF)
├── Historial de proyectos
└── Panel de administración básico
```

**Pantallas clave:**

```
1. Dashboard
   → Proyectos recientes
   → Estadísticas de uso del plan
   → Botón "Nuevo proyecto"

2. Nuevo proyecto
   → Drag & drop del plano
   → Selección de tipo (arq/estructura/instalaciones)
   → Selección de región (para precios)
   → Notas adicionales

3. Procesando
   → Barra de progreso
   → Log de lo que está extrayendo la IA
   → Tiempo estimado restante

4. Resultado
   → Plano con elementos coloreados y anotados
   → Tabla de cubicación editable
   → Presupuesto preliminar
   → Botones: "Exportar Excel" / "Exportar PDF" / "Ajustar"

5. Editor
   → El profesional revisa elemento por elemento
   → Puede corregir medidas, agregar partidas faltantes
   → Sistema guarda las correcciones para mejorar el modelo
```

---

### FASE 3 — Inteligencia y Escala (semanas 17-24)

```
Mejoras con datos reales:
├── Fine-tuning del sistema con correcciones de usuarios
├── Base de precios con actualización automática mensual
├── API pública para integración con otros sistemas
├── Módulo de comparación de versiones de presupuesto
├── Multi-idioma (español regional: Chile, Colombia, México)
├── Integración con Procore / BuilderTrend
└── White label para clientes corporativos
```

---

## 10. BASE DE PRECIOS UNITARIOS

### 10.1 Estructura de la base de datos

```sql
CREATE TABLE precios_unitarios (
    id              SERIAL PRIMARY KEY,
    codigo          VARCHAR(50),        -- Ej: "03.01.001"
    descripcion     TEXT,               -- Ej: "Hormigón H-30 en losa"
    unidad          VARCHAR(20),        -- m3, m2, ml, un
    pais            VARCHAR(50),        -- chile, colombia, mexico
    region          VARCHAR(100),       -- RM, Antofagasta, Bogotá...
    precio_mat      DECIMAL(12,2),      -- Costo materiales
    precio_mo       DECIMAL(12,2),      -- Costo mano de obra
    precio_maq      DECIMAL(12,2),      -- Costo maquinaria
    precio_total    DECIMAL(12,2),      -- Total partida
    fuente          VARCHAR(200),       -- PREOC, SINCO, propio
    fecha_vigencia  DATE,
    activo          BOOLEAN DEFAULT TRUE
);

CREATE TABLE partidas_tipo (
    id          SERIAL PRIMARY KEY,
    codigo      VARCHAR(50),
    nombre      TEXT,
    capitulo    VARCHAR(100),   -- Obras de tierra, Estructuras...
    sinonimos   TEXT[],         -- Para matching con lenguaje natural
    unidad      VARCHAR(20)
);
```

### 10.2 Fuentes de precios por país

```
CHILE:
→ PREOC (Presupuestos y Obras de Construcción)
→ Valores MINVU para vivienda social
→ Cámara Chilena de la Construcción

COLOMBIA:
→ SINCO (Sistema de Información de Costos)
→ SIPE (Sistema de Información de Precios)
→ CAMACOL regional

MÉXICO:
→ CMIC (Cámara Mexicana de la Industria de la Construcción)
→ Precios unitarios INEGI
→ Catálogos estatales de obra pública

PERÚ:
→ CAPECO
→ Revista Costos
→ Precios MVCS (Ministerio de Vivienda)
```

---

## 11. GESTIÓN DE CALIDAD Y VALIDACIÓN

### 11.1 Sistema de confianza por elemento

```python
# Cada elemento extraído tiene score de confianza
{
  "tipo": "muro_exterior",
  "longitud_ml": 12.4,
  "confianza": 0.92,        # 92% seguro
  "fuente": "vision",       # cómo se extrajo
  "requiere_revision": False
}

# Si confianza < 0.70 → marcar para revisión humana
# Si confianza < 0.50 → no incluir, pedir al profesional
```

### 11.2 Reporte de precisión al cliente

```
Con cada entrega incluir:
→ % de elementos con alta confianza (>85%)
→ Lista de elementos que requieren verificación
→ Elementos que el sistema NO pudo extraer
→ Recomendación de dónde revisar manualmente

Esto es transparencia que genera confianza.
El cliente sabe exactamente qué validar.
```

### 11.3 Mejora continua

```python
# Cada corrección del profesional alimenta el sistema
def registrar_correccion(proyecto_id, elemento_original, elemento_corregido):
    """
    Guarda las correcciones para:
    1. Mejorar prompts de Claude
    2. Identificar tipos de planos problemáticos
    3. Calcular métricas de precisión reales
    """
    pass
```

---

## 12. SEGURIDAD Y COMPLIANCE

```
DATOS DEL CLIENTE:
→ Planos encriptados en reposo (AES-256)
→ Transmisión por HTTPS/TLS 1.3
→ Eliminación automática de archivos a los 30 días
→ Opción de eliminación inmediata por el usuario

ACCESO:
→ Autenticación con 2FA opcional
→ Roles: admin, profesional, viewer
→ Log de todas las acciones (auditoría)

LEGAL:
→ Términos de servicio claros sobre responsabilidad
→ El sistema produce un borrador; la firma profesional valida
→ No guardar datos confidenciales del proyecto en prompts
→ Acuerdo de confidencialidad disponible para plan Empresa
```

---

## 13. ROADMAP COMPLETO

```
2026
──────────────────────────────────────────────
MAYO-JUNIO      Fase 0: PoC con Claude Vision
                → 5 planos de prueba
                → Medir precisión real
                → Decisión: ¿seguir o pivotar?

JULIO           Fase 1: MVP CLI
                → Procesamiento PDF completo
                → Generación Excel básico
                → 5 clientes beta gratuitos

AGOSTO          Primeros ingresos (servicio gestionado)
                → Objetivo: $1,500 USD/mes
                → Refinar base de precios Chile

SEPTIEMBRE      Fase 2: Web app básica
                → Upload + procesamiento + descarga
                → Primeros clientes SaaS

OCTUBRE-NOV     Crecimiento SaaS
                → 20-30 clientes pagando
                → Añadir Colombia (precios SINCO)
                → YouTube: 8 videos publicados

DICIEMBRE       Evaluación año 1
                → Objetivo: 50 clientes, $8,000/mes MRR
                → Decisión de inversión año 2

2027
──────────────────────────────────────────────
Q1              Añadir México + Perú
                → Expansión mercado total
                → Primer prospecto white label

Q2              API pública
                → Integraciones con terceros
                → Primer contrato corporativo

Q3-Q4           Escala
                → 150+ clientes SaaS
                → 2-3 contratos corporativos
                → Evaluar ronda de inversión o bootstrapping
```

---

## 14. INVERSIÓN INICIAL REQUERIDA

```
DESARROLLO (con Claude Code, sin developers externos):
→ Tu tiempo: 4-8 semanas
→ Herramientas Claude Code: incluido
→ Costo real: $0 en software

INFRAESTRUCTURA MES 1:
→ VPS básico:          $20
→ Dominio + SSL:       $15
→ Storage:             $10
→ TOTAL:               $45/mes

HERRAMIENTAS NEGOCIO:
→ Email profesional:   $6/mes
→ Notion (docs):       $0 (gratuito)
→ Calendly (reuniones):$0 (gratuito)
→ Stripe (pagos):      % comisión solo si vendes
→ TOTAL:               $6/mes

PRIMER MES CLAUDE API (pruebas):
→ Estimado:            $30-50

──────────────────────────────────────
INVERSIÓN TOTAL MES 1: ~$100-120 USD
──────────────────────────────────────

Para empezar necesitas literalmente $100 y tu tiempo.
```

---

## 15. PRIMER PASO — ESTA SEMANA

```
DÍA 1-2:
□ Instalar dependencias: pip install anthropic ezdxf ifcopenshell pdfplumber openpyxl
□ Conseguir 3 planos reales (PDF) de proyectos conocidos
□ Ejecutar script de PoC con Claude Vision
□ Medir precisión vs cubicación manual conocida

DÍA 3-4:
□ Identificar qué tipos de elementos extrae bien y cuáles falla
□ Ajustar prompts hasta lograr >80% de precisión en elementos obvios
□ Generar primer Excel de cubicación automático

DÍA 5:
□ Contactar 3 constructoras o estudios conocidos
□ Propuesta: "te proceso gratis el próximo proyecto urgente"
□ Agendar llamada de feedback

SEMANA 2:
□ Procesar los 3 proyectos gratuitos
□ Documentar resultados con métricas
□ Iteración del sistema con lo aprendido
□ Definir si el producto tiene tracción real
```

---

*Plan elaborado con Claude Code — Mayo 2026*
*Versión viva: actualizar con resultados reales del mercado*
