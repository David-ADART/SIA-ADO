# agente.R
# Generación de agentes (granjas y mataderos) y de la tabla de conexiones.
# Traducción fiel de simulation.py / instrucciones.md. No dibuja nada.

TIPOS_AGENTE <- c("GC", "GE", "MA")

NOMBRE_TIPO <- c(
  GC = "Granja de cría",
  GE = "Granja de engorde",
  MA = "Matadero"
)

NOMBRE_INFECCION <- c(
  "0" = "Limpio",
  "1" = "Silente",
  "2" = "Declarada",
  "3" = "Desinfección"
)

HAS_COLS <- c("dia", "AID", "AC", "AI", "MI")
HIT_COLS <- c("dia", "X", "Y", "NT", "IT", "IM")
HIM_COLS <- c("dia", "Y", "IMY", "IYM")


valores_por_defecto <- function() {
  # Parámetros iniciales del prototipo (sección 7).
  list(
    T = 60,          # lado del mapa, km
    Nc = 8,          # granjas de cría
    Ne = 12,         # granjas de engorde
    Nm = 3,          # mataderos
    AR = 5,          # radio de seguridad (km)
    PIMS = 0.2,      # P(agente silente → contamina el medio)
    PIME = 0.2,      # P(medio → contamina el agente)
    PITS = 0.9,      # P(agente infectado → contamina el transporte)
    PITE = 0.9,      # P(transporte infectado → contamina el agente)
    DI1 = 3,         # días silente → declarada
    DI2 = 4,         # días declarada → desinfección
    DI3 = 15,        # días desinfección → limpio
    PM = 0.05,       # P(medio A infecta medio B a 1 km)
    semilla = 42,
    max_dias = 365
  )
}


costes_por_defecto <- function() {
  list(
    CFCG = 200,    # fijo / día de cuarentena en granja
    CACG = 4,      # por animal / día en cuarentena (granja)
    CFCM = 300,    # fijo / día de cuarentena en matadero
    CACM = 400,    # por animal no sacrificado / día
    CFLG = 1000,   # fijo / día de limpieza en granja
    CALG = 10,     # por animal eliminado en granja
    CFLM = 600,    # fijo / día de limpieza en matadero
    CALM = 15      # por animal limpiado en matadero
  )
}


clip01 <- function(p) {
  # Una probabilidad vive en [0, 1].
  as.numeric(max(0, min(1, p)))
}


bernoulli <- function(p) {
  # Ensayo de Bernoulli. Devuelve 0 o 1.
  as.integer(stats::runif(1) < clip01(p))
}


empty_has <- function() {
  data.frame(
    dia = integer(0), AID = integer(0), AC = integer(0),
    AI = integer(0), MI = numeric(0), stringsAsFactors = FALSE
  )
}


empty_hit <- function() {
  data.frame(
    dia = integer(0), X = integer(0), Y = integer(0),
    NT = integer(0), IT = integer(0), IM = integer(0),
    stringsAsFactors = FALSE
  )
}


empty_him <- function() {
  data.frame(
    dia = integer(0), Y = integer(0), IMY = integer(0), IYM = integer(0),
    stringsAsFactors = FALSE
  )
}


mezclar_params <- function(params = list()) {
  # Completa un payload parcial con los valores por defecto.
  base <- valores_por_defecto()
  if (is.null(params) || length(params) == 0) return(base)
  for (nm in names(base)) {
    if (!is.null(params[[nm]]) && !identical(params[[nm]], "")) {
      base[[nm]] <- params[[nm]]
    }
  }
  base$T <- as.numeric(base$T)
  base$Nc <- as.integer(base$Nc)
  base$Ne <- as.integer(base$Ne)
  base$Nm <- as.integer(base$Nm)
  base$AR <- as.numeric(base$AR)
  base$PIMS <- as.numeric(base$PIMS)
  base$PIME <- as.numeric(base$PIME)
  base$PITS <- as.numeric(base$PITS)
  base$PITE <- as.numeric(base$PITE)
  base$DI1 <- as.integer(base$DI1)
  base$DI2 <- as.integer(base$DI2)
  base$DI3 <- as.integer(base$DI3)
  base$PM <- as.numeric(base$PM)
  base$semilla <- as.integer(base$semilla)
  base$max_dias <- as.integer(base$max_dias)
  base
}


mezclar_costes <- function(costes = list()) {
  base <- costes_por_defecto()
  if (is.null(costes) || length(costes) == 0) return(base)
  for (nm in names(costes)) {
    if (!is.null(costes[[nm]])) base[[nm]] <- as.numeric(costes[[nm]])
  }
  base
}


posiciones_aleatorias <- function(n, t, min_dist = 1) {
  # Coloca n puntos en [0, T] × [0, T] con distancia euclídea ≥ 1 km.
  if (n <= 0) {
    return(matrix(numeric(0), ncol = 2))
  }
  if (n == 1) {
    return(matrix(stats::runif(2, 0, t), ncol = 2))
  }
  max_intentos_punto <- 500L
  max_reinicios <- 25L
  for (reinicio in seq_len(max_reinicios)) {
    puntos <- matrix(numeric(0), ncol = 2)
    ok <- TRUE
    for (i in seq_len(n)) {
      elegido <- NULL
      for (intento in seq_len(max_intentos_punto)) {
        cand <- stats::runif(2, 0, t)
        if (nrow(puntos) == 0) {
          elegido <- cand
          break
        }
        dx <- puntos[, 1] - cand[1]
        dy <- puntos[, 2] - cand[2]
        if (all(sqrt(dx * dx + dy * dy) >= min_dist - 1e-9)) {
          elegido <- cand
          break
        }
      }
      if (is.null(elegido)) {
        ok <- FALSE
        break
      }
      puntos <- rbind(puntos, elegido)
    }
    if (ok) return(puntos)
  }
  stop(sprintf(
    "No se pueden colocar %d agentes en un cuadrado de %g×%g km con distancia mínima %g km. Sube T o baja Nc+Ne+Nm.",
    n, t, t, min_dist
  ), call. = FALSE)
}


generar_agentes <- function(params, semilla = NULL) {
  # Tabla de agentes (sección 6). AI, AC y MI empiezan a 0.
  params <- mezclar_params(params)
  if (!is.null(semilla)) {
    set.seed(as.integer(semilla))
  } else {
    set.seed(params$semilla)
  }
  nc <- params$Nc
  ne <- params$Ne
  nm <- params$Nm
  t <- params$T
  n <- nc + ne + nm
  if (n <= 0) {
    stop("Hace falta al menos un agente (Nc + Ne + Nm > 0).", call. = FALSE)
  }
  xy <- posiciones_aleatorias(n, t)
  tipos <- c(rep("GC", nc), rep("GE", ne), rep("MA", nm))
  data.frame(
    AID = seq_len(n),
    AT = tipos,
    AX = round(xy[, 1], 3),
    AY = round(xy[, 2], 3),
    AN = as.integer(sample(500:2000, n, replace = TRUE)),
    AI = 0L,
    AC = 0L,
    MI = 0,
    AR = params$AR,
    PIMS = params$PIMS,
    PIME = params$PIME,
    PITS = params$PITS,
    PITE = params$PITE,
    DI1 = params$DI1,
    DI2 = params$DI2,
    DI3 = params$DI3,
    stringsAsFactors = FALSE
  )
}


generar_conexiones <- function(agentes, pm_default = 0.05, semilla = NULL) {
  # Tabla dirigida A → B (N×(N-1) filas). No incluye A → A.
  # M: GC→GE y GE→MA = Bernoulli(0.3) * AN(A) / 2500; resto 0.
  if (!is.null(semilla)) set.seed(as.integer(semilla))
  n <- nrow(agentes)
  if (n <= 1) {
    return(data.frame(
      IDA = integer(0), IDB = integer(0), D = numeric(0),
      V = integer(0), M = numeric(0), PM = numeric(0),
      stringsAsFactors = FALSE
    ))
  }
  filas <- vector("list", n * (n - 1L))
  k <- 0L
  for (i in seq_len(n)) {
    a <- agentes[i, ]
    for (j in seq_len(n)) {
      if (i == j) next
      b <- agentes[j, ]
      dist <- sqrt((a$AX - b$AX)^2 + (a$AY - b$AY)^2)
      v <- as.integer(dist <= a$AR)
      if (a$AT == "GC" && b$AT == "GE") {
        m <- bernoulli(0.3) * a$AN / 2500
      } else if (a$AT == "GE" && b$AT == "MA") {
        m <- bernoulli(0.3) * a$AN / 2500
      } else {
        m <- 0
      }
      k <- k + 1L
      filas[[k]] <- data.frame(
        IDA = as.integer(a$AID),
        IDB = as.integer(b$AID),
        D = round(dist, 4),
        V = v,
        M = round(as.numeric(m), 4),
        PM = as.numeric(pm_default),
        stringsAsFactors = FALSE
      )
    }
  }
  do.call(rbind, filas[seq_len(k)])
}


actualizar_vigilancia <- function(agentes, conexiones) {
  # Recalcula V cuando el usuario cambia AR.
  if (nrow(conexiones) == 0) return(conexiones)
  ar <- setNames(agentes$AR, agentes$AID)
  conexiones$V <- as.integer(conexiones$D <= as.numeric(ar[as.character(conexiones$IDA)]))
  conexiones
}


as_agentes_df <- function(obj) {
  # Convierte JSON (lista o data.frame) a la tabla de agentes.
  if (is.null(obj) || (is.data.frame(obj) && nrow(obj) == 0) || length(obj) == 0) {
    return(NULL)
  }
  df <- as.data.frame(obj, stringsAsFactors = FALSE)
  need <- c("AID", "AT", "AX", "AY", "AN", "AI", "AC", "MI",
            "AR", "PIMS", "PIME", "PITS", "PITE", "DI1", "DI2", "DI3")
  for (col in need) {
    if (!col %in% names(df)) {
      stop(sprintf("Falta la columna de agente '%s'.", col), call. = FALSE)
    }
  }
  df$AID <- as.integer(df$AID)
  df$AT <- as.character(df$AT)
  df$AX <- as.numeric(df$AX)
  df$AY <- as.numeric(df$AY)
  df$AN <- as.integer(df$AN)
  df$AI <- as.integer(df$AI)
  df$AC <- as.integer(df$AC)
  df$MI <- as.numeric(df$MI)
  df$AR <- as.numeric(df$AR)
  df$PIMS <- as.numeric(df$PIMS)
  df$PIME <- as.numeric(df$PIME)
  df$PITS <- as.numeric(df$PITS)
  df$PITE <- as.numeric(df$PITE)
  df$DI1 <- as.integer(df$DI1)
  df$DI2 <- as.integer(df$DI2)
  df$DI3 <- as.integer(df$DI3)
  df
}


as_conexiones_df <- function(obj) {
  if (is.null(obj) || (is.data.frame(obj) && nrow(obj) == 0) || length(obj) == 0) {
    return(NULL)
  }
  df <- as.data.frame(obj, stringsAsFactors = FALSE)
  need <- c("IDA", "IDB", "D", "V", "M")
  for (col in need) {
    if (!col %in% names(df)) {
      stop(sprintf("Falta la columna de conexión '%s'.", col), call. = FALSE)
    }
  }
  if (!"PM" %in% names(df)) df$PM <- 0.05
  df$IDA <- as.integer(df$IDA)
  df$IDB <- as.integer(df$IDB)
  df$D <- as.numeric(df$D)
  df$V <- as.integer(df$V)
  df$M <- as.numeric(df$M)
  df$PM <- as.numeric(df$PM)
  df
}
