-- Esquema de base de datos para PostgreSQL
-- Automatización y Software del Bajío - Sistema de Tickets de Mantenimiento
-- Soporte completo para HU-01 a HU-09 (Sprints 1, 2 y 3)

CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    nombre_completo VARCHAR(150) NOT NULL,
    rol VARCHAR(30) NOT NULL CHECK(rol IN ('Admin', 'Usuario', 'Responsable')),
    estado VARCHAR(20) NOT NULL DEFAULT 'Activo' CHECK(estado IN ('Activo', 'Inactivo')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS areas (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,
    nombre VARCHAR(150) UNIQUE NOT NULL,
    descripcion TEXT,
    estado VARCHAR(20) NOT NULL DEFAULT 'Activo' CHECK(estado IN ('Activo', 'Inactivo')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS catalogos (
    id SERIAL PRIMARY KEY,
    tipo VARCHAR(50) NOT NULL,
    clave VARCHAR(50) NOT NULL,
    valor VARCHAR(150) NOT NULL,
    descripcion TEXT,
    estado VARCHAR(20) NOT NULL DEFAULT 'Activo' CHECK(estado IN ('Activo', 'Inactivo')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS equipos (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,
    nombre VARCHAR(150) NOT NULL,
    marca VARCHAR(100) NOT NULL,
    modelo VARCHAR(100) NOT NULL,
    numero_serie VARCHAR(100) UNIQUE NOT NULL,
    area_id INTEGER NOT NULL REFERENCES areas(id),
    ubicacion_especifica TEXT,
    periodicidad_dias INTEGER NOT NULL DEFAULT 90,
    fecha_ultimo_mantenimiento DATE,
    estado VARCHAR(30) NOT NULL DEFAULT 'Activo' CHECK(estado IN ('Activo', 'Inactivo', 'En Mantenimiento', 'Fuera de Servicio')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,
    titulo VARCHAR(255) NOT NULL,
    descripcion TEXT NOT NULL,
    situacion_problema TEXT,
    detector_nombre VARCHAR(150),
    categoria VARCHAR(100) NOT NULL,
    prioridad VARCHAR(20) NOT NULL CHECK(prioridad IN ('Baja', 'Media', 'Alta', 'Urgente')),
    estado VARCHAR(30) NOT NULL DEFAULT 'Abierto' CHECK(estado IN ('Abierto', 'En Proceso', 'En Espera', 'Resuelto', 'Cerrado', 'Cancelado', 'Duplicado')),
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

CREATE TABLE IF NOT EXISTS ticket_adjuntos (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    usuario_id INTEGER REFERENCES usuarios(id),
    nombre_archivo VARCHAR(255) NOT NULL,
    nombre_original VARCHAR(255) NOT NULL,
    tamano_bytes BIGINT NOT NULL,
    tamano_formateado VARCHAR(50) NOT NULL,
    mime_type VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ticket_historial (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    accion VARCHAR(100) NOT NULL,
    comentario TEXT,
    estado_anterior VARCHAR(30),
    estado_nuevo VARCHAR(30),
    responsable_anterior_id INTEGER REFERENCES usuarios(id),
    responsable_nuevo_id INTEGER REFERENCES usuarios(id),
    motivo_detalle TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pg_usuarios_email ON usuarios(email);
CREATE INDEX IF NOT EXISTS idx_pg_equipos_codigo ON equipos(codigo);
CREATE INDEX IF NOT EXISTS idx_pg_tickets_codigo ON tickets(codigo);
CREATE INDEX IF NOT EXISTS idx_pg_tickets_solicitante ON tickets(solicitante_id);
CREATE INDEX IF NOT EXISTS idx_pg_tickets_responsable ON tickets(responsable_id);
CREATE INDEX IF NOT EXISTS idx_pg_tickets_equipo ON tickets(equipo_id);
