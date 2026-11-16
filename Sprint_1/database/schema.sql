-- Esquema de base de datos para Sistema de Tickets de Mantenimiento
-- Automatización y Software del Bajío
-- Soporte completo para HU-01 a HU-09 (Sprints 1, 2 y 3)

-- 1. Tabla de Usuarios (HU-01, HU-02, HU-03)
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL COLLATE NOCASE,
    email TEXT UNIQUE NOT NULL COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    nombre_completo TEXT NOT NULL,
    rol TEXT NOT NULL CHECK(rol IN ('Admin', 'Usuario', 'Responsable')),
    estado TEXT NOT NULL DEFAULT 'Activo' CHECK(estado IN ('Activo', 'Inactivo')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tabla de Áreas / Ubicaciones (HU-04)
CREATE TABLE IF NOT EXISTS areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE NOT NULL COLLATE NOCASE,
    nombre TEXT UNIQUE NOT NULL,
    descripcion TEXT,
    estado TEXT NOT NULL DEFAULT 'Activo' CHECK(estado IN ('Activo', 'Inactivo')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tabla de Catálogos Auxiliares (HU-04)
CREATE TABLE IF NOT EXISTS catalogos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    clave TEXT NOT NULL,
    valor TEXT NOT NULL,
    descripcion TEXT,
    estado TEXT NOT NULL DEFAULT 'Activo' CHECK(estado IN ('Activo', 'Inactivo')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Tabla de Equipos / Activos Industriales (HU-04)
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

-- 5. Tabla de Tickets (HU-02, HU-05, HU-06, HU-07, HU-08, HU-09)
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
    motivo_reasignacion TEXT,
    motivo_espera TEXT,
    motivo_cancelacion TEXT,
    fecha_inicio_atencion TIMESTAMP,
    fecha_resolucion TIMESTAMP,
    fecha_cierre TIMESTAMP,
    tiempo_espera_minutos INTEGER DEFAULT 0,
    ultima_fecha_espera TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Tabla de Evidencias y Archivos Adjuntos (HU-05, HU-09: <= 10 MB)
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

-- 7. Tabla de Historial, Bitácora y Auditoría Inmutable (HU-02, HU-07, HU-08, HU-09)
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices de Rendimiento, Búsqueda Rápida y Auditoría
CREATE INDEX IF NOT EXISTS idx_usuarios_username ON usuarios(username);
CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);
CREATE INDEX IF NOT EXISTS idx_equipos_codigo ON equipos(codigo);
CREATE INDEX IF NOT EXISTS idx_equipos_area ON equipos(area_id);
CREATE INDEX IF NOT EXISTS idx_equipos_estado ON equipos(estado);
CREATE INDEX IF NOT EXISTS idx_tickets_codigo ON tickets(codigo);
CREATE INDEX IF NOT EXISTS idx_tickets_solicitante ON tickets(solicitante_id);
CREATE INDEX IF NOT EXISTS idx_tickets_responsable ON tickets(responsable_id);
CREATE INDEX IF NOT EXISTS idx_tickets_equipo ON tickets(equipo_id);
CREATE INDEX IF NOT EXISTS idx_tickets_area ON tickets(area_id);
CREATE INDEX IF NOT EXISTS idx_tickets_estado ON tickets(estado);
CREATE INDEX IF NOT EXISTS idx_tickets_prioridad ON tickets(prioridad);
CREATE INDEX IF NOT EXISTS idx_tickets_relacionado ON tickets(ticket_relacionado_id);
CREATE INDEX IF NOT EXISTS idx_historial_ticket ON ticket_historial(ticket_id);
CREATE INDEX IF NOT EXISTS idx_adjuntos_ticket ON ticket_adjuntos(ticket_id);
