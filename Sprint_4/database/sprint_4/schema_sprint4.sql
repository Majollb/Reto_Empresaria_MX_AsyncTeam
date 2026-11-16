-- =========================================================================
-- ESQUEMA SPRINT 4: CIERRE, RESOLUCIÓN, RECURRENCIA, AUDITORÍA Y REPORTES
-- Historias de Usuario: HU-10, HU-11, HU-12
-- Automatización y Software del Bajío
-- =========================================================================

-- Tabla de Tickets Extendida para Sprint 4:
-- - HU-10: Cierre con solución, cierre sin solución justificado, inmutabilidad tras cierre,
--          y creación de atención nueva relacionada por recurrencia.
-- - HU-11: Trazabilidad cronológica completa y consulta inmutable de eventos.
-- - HU-12: Resumen ejecutivo, conteos por situaciones, semáforo preventivo y exportación CSV.

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE NOT NULL,
    titulo TEXT NOT NULL,
    descripcion TEXT NOT NULL,
    situacion_problema TEXT,
    detector_nombre TEXT,
    categoria TEXT NOT NULL,
    prioridad TEXT NOT NULL CHECK(prioridad IN ('Baja', 'Media', 'Alta', 'Urgente')),
    estado TEXT NOT NULL DEFAULT 'Abierto' CHECK(estado IN ('Abierto', 'En Proceso', 'En Espera', 'Resuelto', 'Cerrado', 'Cancelado', 'Duplicado')),
    solicitante_id INTEGER NOT NULL REFERENCES usuarios(id),
    responsable_id INTEGER REFERENCES usuarios(id),
    equipo_id INTEGER REFERENCES equipos(id),
    area_id INTEGER REFERENCES areas(id),
    ubicacion_equipo TEXT,
    ticket_relacionado_id INTEGER REFERENCES tickets(id),
    tipo_relacion TEXT CHECK(tipo_relacion IN ('Duplicado', 'Recurrencia', NULL)),
    motivo_reasignacion TEXT,
    motivo_espera TEXT,
    motivo_cancelacion TEXT,
    tipo_cierre TEXT CHECK(tipo_cierre IN ('Con Solución', 'Sin Solución', NULL)),
    solucion_detalle TEXT,
    motivo_sin_solucion TEXT,
    es_recurrencia INTEGER DEFAULT 0 CHECK(es_recurrencia IN (0, 1)),
    ticket_origen_recurrencia_id INTEGER REFERENCES tickets(id),
    fecha_inicio_atencion TIMESTAMP,
    fecha_resolucion TIMESTAMP,
    fecha_cierre TIMESTAMP,
    tiempo_espera_minutos INTEGER DEFAULT 0,
    ultima_fecha_espera TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Evidencias Técnicas Adicionales (HU-05, HU-09, HU-10: <= 10 MB)
CREATE TABLE IF NOT EXISTS ticket_adjuntos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    usuario_id INTEGER REFERENCES usuarios(id),
    nombre_archivo TEXT NOT NULL,
    nombre_original TEXT NOT NULL,
    tamano_bytes INTEGER NOT NULL,
    tamano_formateado TEXT NOT NULL,
    mime_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Historial, Bitácora y Auditoría Inmutable (HU-02, HU-07, HU-08, HU-09, HU-11)
CREATE TABLE IF NOT EXISTS ticket_historial (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    accion TEXT NOT NULL,
    comentario TEXT,
    estado_anterior TEXT,
    estado_nuevo TEXT,
    responsable_anterior_id INTEGER REFERENCES usuarios(id),
    responsable_nuevo_id INTEGER REFERENCES usuarios(id),
    motivo_detalle TEXT,
    tipo_evento TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices de Rendimiento para Reportes y Trazabilidad (HU-11, HU-12)
CREATE INDEX IF NOT EXISTS idx_tickets_tipo_cierre ON tickets(tipo_cierre);
CREATE INDEX IF NOT EXISTS idx_tickets_es_recurrencia ON tickets(es_recurrencia);
CREATE INDEX IF NOT EXISTS idx_tickets_recurrencia_origen ON tickets(ticket_origen_recurrencia_id);
CREATE INDEX IF NOT EXISTS idx_tickets_tipo_relacion ON tickets(tipo_relacion);
CREATE INDEX IF NOT EXISTS idx_historial_tipo_evento ON ticket_historial(tipo_evento);
