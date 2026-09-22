# analitica.R
# Series temporales, costes y el resumen estadístico final (JSON de /simular).


series_estados <- function(has, agentes) {
  # Nº de agentes y de animales en silente / declarada / desinfección / cuarentena.
  if (nrow(has) == 0) {
    return(data.frame(
      dia = integer(0), n_silente = integer(0), n_declarada = integer(0),
      n_desinfeccion = integer(0), n_cuarentena = integer(0),
      anim_silente = integer(0), anim_declarada = integer(0),
      anim_desinfeccion = integer(0), anim_cuarentena = integer(0),
      stringsAsFactors = FALSE
    ))
  }
  an <- setNames(agentes$AN, agentes$AID)
  has$AN <- as.numeric(an[as.character(has$AID)])
  has$AN[is.na(has$AN)] <- 0
  dias <- sort(unique(has$dia))
  filas <- lapply(dias, function(dia) {
    g <- has[has$dia == dia, ]
    data.frame(
      dia = as.integer(dia),
      n_silente = as.integer(sum(g$AI == 1L)),
      n_declarada = as.integer(sum(g$AI == 2L)),
      n_desinfeccion = as.integer(sum(g$AI == 3L)),
      n_cuarentena = as.integer(sum(g$AC == 1L)),
      anim_silente = as.integer(sum(g$AN[g$AI == 1L])),
      anim_declarada = as.integer(sum(g$AN[g$AI == 2L])),
      anim_desinfeccion = as.integer(sum(g$AN[g$AI == 3L])),
      anim_cuarentena = as.integer(sum(g$AN[g$AC == 1L])),
      stringsAsFactors = FALSE
    )
  })
  do.call(rbind, filas)
}


series_costes <- function(has, agentes, costes) {
  # Costes diarios (sección 7).
  # Cuarentena granja:  CFCG + CACG * AN   si AC=1
  # Cuarentena matadero: CFCM + CACM * AN  si AC=1
  # Limpieza granja:    CFLG + CALG * AN   si AI=3
  # Limpieza matadero:  CFLM + CALM * AN   si AI=3
  costes <- mezclar_costes(costes)
  vacio <- data.frame(
    dia = integer(0), c_c_granja = numeric(0), c_c_mata = numeric(0),
    c_l_granja = numeric(0), c_l_mata = numeric(0), c_total = numeric(0),
    stringsAsFactors = FALSE
  )
  if (nrow(has) == 0) return(vacio)
  meta <- agentes[, c("AID", "AT", "AN")]
  h <- merge(has, meta, by = "AID", all.x = TRUE, sort = FALSE)
  es_granja <- h$AT %in% c("GC", "GE")
  es_mata <- h$AT == "MA"
  en_c <- h$AC == 1L
  en_l <- h$AI == 3L
  h$c_c_granja <- ifelse(es_granja & en_c, costes$CFCG + costes$CACG * h$AN, 0)
  h$c_c_mata <- ifelse(es_mata & en_c, costes$CFCM + costes$CACM * h$AN, 0)
  h$c_l_granja <- ifelse(es_granja & en_l, costes$CFLG + costes$CALG * h$AN, 0)
  h$c_l_mata <- ifelse(es_mata & en_l, costes$CFLM + costes$CALM * h$AN, 0)
  dias <- sort(unique(h$dia))
  filas <- lapply(dias, function(dia) {
    g <- h[h$dia == dia, ]
    cg <- sum(g$c_c_granja)
    cm <- sum(g$c_c_mata)
    lg <- sum(g$c_l_granja)
    lm <- sum(g$c_l_mata)
    data.frame(
      dia = as.integer(dia),
      c_c_granja = cg, c_c_mata = cm,
      c_l_granja = lg, c_l_mata = lm,
      c_total = cg + cm + lg + lm,
      stringsAsFactors = FALSE
    )
  })
  do.call(rbind, filas)
}


pico_serie <- function(ser, col) {
  if (nrow(ser) == 0) return(list(valor = 0, dia = 0L))
  v <- ser[[col]]
  i <- which.max(v)
  list(valor = as.numeric(v[i]), dia = as.integer(ser$dia[i]))
}


resumen_estadistico <- function(teatro) {
  # Cierra el experimento: series, costes y un bloque "estadisticos"
  # pensado para el JSON de /simular.
  ser <- series_estados(teatro$has, teatro$agentes)
  sco <- series_costes(teatro$has, teatro$agentes, teatro$costes)
  n <- nrow(teatro$agentes)
  n_hit_inf <- if (nrow(teatro$hit) == 0) 0L else as.integer(sum(teatro$hit$IT == 1L))
  n_im_medio <- if (nrow(teatro$hit) == 0) 0L else as.integer(sum(teatro$hit$IM == 1L))
  n_imy <- if (nrow(teatro$him) == 0) 0L else as.integer(sum(teatro$him$IMY == 1L))
  n_iym <- if (nrow(teatro$him) == 0) 0L else as.integer(sum(teatro$him$IYM == 1L))
  list(
    params = teatro$params,
    costes = teatro$costes,
    brotes = as.integer(teatro$brotes),
    dia_final = as.integer(teatro$day),
    estable = isTRUE(teatro$estable),
    n_agentes = as.integer(n),
    estadisticos = list(
      pico_silente = pico_serie(ser, "n_silente"),
      pico_declarada = pico_serie(ser, "n_declarada"),
      pico_desinfeccion = pico_serie(ser, "n_desinfeccion"),
      pico_cuarentena = pico_serie(ser, "n_cuarentena"),
      pico_animales_silente = pico_serie(ser, "anim_silente"),
      pico_animales_declarada = pico_serie(ser, "anim_declarada"),
      infecciones_transporte = n_hit_inf,
      infecciones_medio_medio = n_im_medio,
      infecciones_medio_agente = n_imy,
      infecciones_agente_medio = n_iym,
      coste_acumulado = if (nrow(sco) == 0) 0 else as.numeric(sum(sco$c_total)),
      coste_cuarentena_granjas = if (nrow(sco) == 0) 0 else as.numeric(sum(sco$c_c_granja)),
      coste_cuarentena_mataderos = if (nrow(sco) == 0) 0 else as.numeric(sum(sco$c_c_mata)),
      coste_limpieza_granjas = if (nrow(sco) == 0) 0 else as.numeric(sum(sco$c_l_granja)),
      coste_limpieza_mataderos = if (nrow(sco) == 0) 0 else as.numeric(sum(sco$c_l_mata))
    ),
    agentes = teatro$agentes,
    conexiones = teatro$conexiones,
    has = teatro$has,
    hit = teatro$hit,
    him = teatro$him,
    series_estados = ser,
    series_costes = sco
  )
}
