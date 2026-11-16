-- =========================================================================
-- ESQUEMA SPRINT 2: CATÁLOGOS, EQUIPOS, PERIODICIDAD, REGISTRO Y FILTRADO
-- Historias de Usuario: HU-04, HU-05, HU-06
-- Automatización y Software del Bajío
-- =========================================================================

-- 1. Tabla de Áreas / Ubicaciones (HU-04)
CREATE TABLE IF NOT EXISTS areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE NOT NULL COLLATE NOCASE,
    nombre TEXT UNIQUE NOT NULL,
    descripcion TEXT,
    estado TEXT NOT NULL DEFAULT 'Activo' CHECK(estado IN ('Activo', 'Inactivo')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tabla de Catálogos Auxiliares (HU-04)
CREATE TABLE IF NOT EXISTS catalogos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    clave TEXT NOT NULL,
    valor TEXT NOT NULL,
    descripcion TEXT,
    estado TEXT NOT NULL DEFAULT 'Activo' CHECK(estado IN ('Activo', 'Inactivo')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tabla de Equipos Industriales y Periodicidad Preventiva (HU-04)
CREATE TABLE IF NOT EXISTS equipos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE NOT NULL COLLATE NOCASE,
    nombre TEXT NOT NULL,
    marca TEXT NOT NULL,
    modelo TEXT NOT NULL,
    numero_serie TEXT UNIQUE NOT NULL,
    area_id INTEGER NOT NULL REFERENCES areas(id),
    ubicacion_especifica TEXT,
    periodicidad_dias INTEGER NOT NULL DEFAULT 90,
    fecha_ultimo_mantenimiento DATE,
    estado TEXT NOT NULL DEFAULT 'Activo' CHECK(estado IN ('Activo', 'Inactivo', 'En Mantenimiento', 'Fuera de Servicio')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Tabla de Tickets Base para Registro y Filtros (HU-05 y HU-06)
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE NOT NULL,
    titulo TEXT NOT NULL,
    descripcion TEXT NOT NULL,
    situacion_problema TEXT,
    detector_nombre TEXT,
    categoria TEXT NOT NULL,
    prioridad TEXT NOT NULL CHECK(prioridad IN ('Baja', 'Media', 'Alta', 'Urgente')),
    estado TEXT NOT NULL DEFAULT 'Abierto' CHECK(estado IN ('Abierto', 'En Proceso', 'En Espera', 'Resuelto', 'Cerrado')),
    solicitante_id INTEGER NOT NULL REFERENCES usuarios(id),
    responsable_id INTEGER REFERENCES usuarios(id),
    equipo_id INTEGER REFERENCES equipos(id),
    area_id INTEGER REFERENCES areas(id),
    ubicacion_equipo TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Tabla de Adjuntos Técnicos <= 10 MB (HU-05)
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

CREATE INDEX IF NOT EXISTS idx_equipos_area ON equipos(area_id);
CREATE INDEX IF NOT EXISTS idx_tickets_codigo ON tickets(codigo);
CREATE INDEX IF NOT EXISTS idx_tickets_solicitante ON tickets(solicitante_id);
CREATE INDEX IF NOT EXISTS idx_tickets_responsable ON tickets(responsable_id);

