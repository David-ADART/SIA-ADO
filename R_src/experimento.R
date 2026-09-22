# experimento.R
# Orquesta un experimento completo: generar teatro, sembrar brote
# y simular día a día hasta que el sistema se estabilice.


crear_teatro <- function(params = list(), semilla = NULL) {
  # Genera agentes y conexiones a partir de los parámetros del modelo.
  params <- mezclar_params(params)
  seed <- if (is.null(semilla)) params$semilla else as.integer(semilla)
  set.seed(seed)
  agentes <- generar_agentes(params, semilla = seed)
  # Continuamos el mismo flujo aleatorio para M (Bernoulli de transportes).
  conexiones <- generar_conexiones(agentes, pm_default = params$PM, semilla = NULL)
  list(
    params = params,
    agentes = agentes,
    conexiones = conexiones,
    has = snapshot_dia0(agentes),
    hit = empty_hit(),
    him = empty_him(),
    day = 0L
  )
}


preparar_brote <- function(teatro, brotes = integer(0)) {
  # Siembra AI=1 en el día 0. Si no hay brotes, se elige el primer GC (o el AID 1).
  agentes <- teatro$agentes
  brotes <- as.integer(unlist(brotes))
  brotes <- brotes[!is.na(brotes)]
  if (length(brotes) == 0 && nrow(agentes) > 0) {
    gc <- agentes$AID[agentes$AT == "GC"]
    brotes <- if (length(gc) > 0) gc[1] else agentes$AID[1]
  }
  agentes <- marcar_brote(agentes, brotes)
  teatro$agentes <- agentes
  teatro$has <- snapshot_dia0(agentes)
  teatro$hit <- empty_hit()
  teatro$him <- empty_him()
  teatro$day <- 0L
  teatro$brotes <- as.integer(brotes)
  teatro
}


paso_experimento <- function(teatro) {
  # Simula el día siguiente. Devuelve el teatro actualizado.
  if (nrow(teatro$agentes) == 0) return(teatro)
  if (sistema_estable(teatro$agentes) && teatro$day > 0) return(teatro)
  seed <- as.integer(teatro$params$semilla) + 10007L * (as.integer(teatro$day) + 1L)
  set.seed(seed)
  out <- simular_un_dia(
    agentes = teatro$agentes,
    conexiones = teatro$conexiones,
    has = teatro$has,
    hit = teatro$hit,
    him = teatro$him,
    dia_anterior = teatro$day
  )
  teatro$agentes <- out$agentes
  teatro$has <- out$has
  teatro$hit <- out$hit
  teatro$him <- out$him
  teatro$day <- as.integer(teatro$day) + 1L
  teatro
}


ejecutar_simulacion <- function(teatro, max_dias = NULL) {
  # Bucle diario hasta AI=0 y MI=0 en todos, o hasta max_dias.
  if (is.null(max_dias)) max_dias <- as.integer(teatro$params$max_dias)
  max_dias <- as.integer(max_dias)
  while (teatro$day < max_dias) {
    if (sistema_estable(teatro$agentes) && teatro$day > 0) break
    teatro <- paso_experimento(teatro)
    if (sistema_estable(teatro$agentes)) break
  }
  teatro$estable <- sistema_estable(teatro$agentes)
  teatro
}


ejecutar_experimento <- function(params = list(), brotes = integer(0),
                                 agentes = NULL, conexiones = NULL,
                                 costes = NULL) {
  # Experimento de extremo a extremo usado por la API /simular.
  params <- mezclar_params(params)
  costes <- mezclar_costes(costes)
  if (is.null(agentes)) {
    teatro <- crear_teatro(params)
  } else {
    if (is.null(conexiones)) {
      set.seed(params$semilla)
      conexiones <- generar_conexiones(agentes, pm_default = params$PM)
    }
    teatro <- list(
      params = params,
      agentes = agentes,
      conexiones = conexiones,
      has = snapshot_dia0(agentes),
      hit = empty_hit(),
      him = empty_him(),
      day = 0L
    )
  }
  teatro <- preparar_brote(teatro, brotes)
  teatro <- ejecutar_simulacion(teatro, max_dias = params$max_dias)
  teatro$costes <- costes
  teatro
}
