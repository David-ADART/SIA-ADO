# ciclo.R
# Un paso diario de la simulación (sección 4 de instrucciones.md):
#   1) cuarentena a partir de AI del día anterior
#   2) infección del agente (transporte + medio propio)
#   3) infección del medio natural


indice_has <- function(has) {
  # Diccionarios "dia:AID" → MI / AI para no filtrar HAS en cada consulta.
  mi <- list()
  ai <- list()
  if (nrow(has) == 0) return(list(mi = mi, ai = ai))
  for (i in seq_len(nrow(has))) {
    clave <- paste(as.integer(has$dia[i]), as.integer(has$AID[i]), sep = ":")
    mi[[clave]] <- as.numeric(has$MI[i])
    ai[[clave]] <- as.integer(has$AI[i])
  }
  list(mi = mi, ai = ai)
}


mi_en_dia <- function(mi_idx, aid, dia) {
  # Días negativos (antes del inicio) valen 0.
  if (dia < 0) return(0)
  clave <- paste(as.integer(dia), as.integer(aid), sep = ":")
  val <- mi_idx[[clave]]
  if (is.null(val)) 0 else as.numeric(val)
}


dias_en_estado <- function(ai_idx, aid, ai_prev, dia_prev) {
  # Días consecutivos (incluyendo dia_prev) con el mismo AI. Sirve para DI1/DI2/DI3.
  if (dia_prev < 0) return(0L)
  cuenta <- 0L
  d <- as.integer(dia_prev)
  while (d >= 0) {
    clave <- paste(d, as.integer(aid), sep = ":")
    val <- ai_idx[[clave]]
    if (is.null(val) || as.integer(val) != as.integer(ai_prev)) break
    cuenta <- cuenta + 1L
    d <- d - 1L
  }
  cuenta
}


prob_desde_lags <- function(pm, mis, distancia = NULL) {
  # P(al menos uno de los 3 días anteriores propaga):
  #   1 - Π_k (1 - pm * MI_{d-k} [/ max(1, D)])
  # Sin distancia: medio de Y → agente Y (PIME).
  # Con distancia: medio de X → medio de Y (PM / max(1, D)).
  sobrevive <- 1
  for (mi in mis) {
    term <- pm * as.numeric(mi)
    if (!is.null(distancia)) {
      term <- term / max(1, as.numeric(distancia))
    }
    sobrevive <- sobrevive * (1 - clip01(term))
  }
  clip01(1 - sobrevive)
}


snapshot_dia0 <- function(agentes) {
  # HAS del día 0: foto inicial, antes de simular.
  if (nrow(agentes) == 0) return(empty_has())
  data.frame(
    dia = 0L,
    AID = as.integer(agentes$AID),
    AC = as.integer(agentes$AC),
    AI = as.integer(agentes$AI),
    MI = as.numeric(agentes$MI),
    stringsAsFactors = FALSE
  )
}


sistema_estable <- function(agentes) {
  # Parada: todos los agentes limpios y todo el medio a 0.
  if (nrow(agentes) == 0) return(TRUE)
  all(agentes$AI == 0) && all(agentes$MI == 0)
}


agentes_en_dia <- function(agentes, has, dia) {
  # Combina la ficha fija del agente con AI/AC/MI de un día concreto.
  if (nrow(agentes) == 0 || nrow(has) == 0) return(agentes)
  snap <- has[has$dia == as.integer(dia), c("AID", "AI", "AC", "MI")]
  if (nrow(snap) == 0) return(agentes)
  base <- agentes[, setdiff(names(agentes), c("AI", "AC", "MI")), drop = FALSE]
  merge(base, snap, by = "AID", all.x = TRUE, sort = FALSE)
}


marcar_brote <- function(agentes, aids) {
  # Pone infección silente (AI=1) en los AID indicados; el resto queda limpio.
  if (nrow(agentes) == 0) return(agentes)
  agentes$AI <- 0L
  if (length(aids) > 0) {
    agentes$AI[agentes$AID %in% as.integer(aids)] <- 1L
  }
  agentes
}


simular_un_dia <- function(agentes, conexiones, has, hit, him, dia_anterior) {
  # Avanza el sistema un día. Devuelve lista(agentes, has, hit, him).
  d <- as.integer(dia_anterior) + 1L
  prev <- agentes
  nuevo <- agentes
  ids <- as.integer(prev$AID)
  idx_aid <- setNames(seq_len(nrow(prev)), prev$AID)

  idx <- indice_has(has)
  mi_idx <- idx$mi
  ai_idx <- idx$ai

  dist <- list()
  m_ab <- list()
  pm_ab <- list()
  en_radio <- lapply(ids, function(x) integer(0))
  names(en_radio) <- as.character(ids)
  hacia <- lapply(ids, function(x) integer(0))
  names(hacia) <- as.character(ids)

  if (nrow(conexiones) > 0) {
    for (r in seq_len(nrow(conexiones))) {
      ida <- as.integer(conexiones$IDA[r])
      idb <- as.integer(conexiones$IDB[r])
      clave <- paste(ida, idb, sep = ":")
      dist[[clave]] <- as.numeric(conexiones$D[r])
      m_ab[[clave]] <- as.numeric(conexiones$M[r])
      pm_ab[[clave]] <- if ("PM" %in% names(conexiones)) as.numeric(conexiones$PM[r]) else 0.05
      if (as.integer(conexiones$V[r]) == 1L) {
        en_radio[[as.character(ida)]] <- c(en_radio[[as.character(ida)]], idb)
      }
      if (as.numeric(conexiones$M[r]) > 0) {
        hacia[[as.character(idb)]] <- c(hacia[[as.character(idb)]], ida)
      }
    }
  }

  hit_rows <- list()
  him_rows <- list()
  it_hacia <- lapply(ids, function(x) integer(0))
  names(it_hacia) <- as.character(ids)
  im_agente <- setNames(rep(0L, length(ids)), ids)

  # ------------------------------------------------------------------
  # 1. Cuarentena
  #    Y entra en cuarentena si AYER él o alguien dentro de su radio
  #    tenía infección declarada (2) o desinfección (3).
  # ------------------------------------------------------------------
  for (i in seq_len(nrow(prev))) {
    aid <- as.integer(prev$AID[i])
    ids_a_mirar <- unique(c(aid, en_radio[[as.character(aid)]]))
    hay_alerta <- FALSE
    for (x in ids_a_mirar) {
      ix <- idx_aid[[as.character(x)]]
      if (!is.null(ix) && as.integer(prev$AI[ix]) %in% c(2L, 3L)) {
        hay_alerta <- TRUE
        break
      }
    }
    nuevo$AC[i] <- if (hay_alerta) 1L else 0L
  }

  # ------------------------------------------------------------------
  # 2. Estado de infección del agente
  # ------------------------------------------------------------------
  for (i in seq_len(nrow(prev))) {
    row <- prev[i, ]
    aid <- as.integer(row$AID)
    ai_prev <- as.integer(row$AI)
    dias_estado <- dias_en_estado(ai_idx, aid, ai_prev, dia_anterior)
    ai_nuevo <- ai_prev
    imy <- 0L

    if (ai_prev == 3L && dias_estado >= as.integer(row$DI3)) {
      ai_nuevo <- 0L
    } else if (ai_prev == 2L && dias_estado >= as.integer(row$DI2)) {
      ai_nuevo <- 3L
    } else if (ai_prev == 1L && dias_estado >= as.integer(row$DI1)) {
      ai_nuevo <- 2L
    } else if (ai_prev == 0L) {
      origenes <- hacia[[as.character(aid)]]
      if (length(origenes) > 0) {
        for (x in origenes) {
          ix <- idx_aid[[as.character(x)]]
          if (is.null(ix)) next
          if (as.integer(prev$AC[ix]) != 0L) {
            nt <- 0L
            it <- 0L
          } else {
            lam <- m_ab[[paste(x, aid, sep = ":")]]
            if (is.null(lam)) lam <- 0
            nt <- if (lam > 0) as.integer(stats::rpois(1, lam)) else 0L
            x_infectado <- as.integer(prev$AI[ix] != 0L)
            pit1 <- x_infectado * as.numeric(prev$PITS[ix]) * as.numeric(row$PITE)
            pit_dia <- if (nt > 0) 1 - (1 - clip01(pit1))^nt else 0
            it <- if (nt > 0) bernoulli(pit_dia) else 0L
          }
          it_hacia[[as.character(aid)]] <- c(it_hacia[[as.character(aid)]], it)
          hit_rows[[length(hit_rows) + 1L]] <- data.frame(
            dia = d, X = as.integer(x), Y = aid,
            NT = nt, IT = it, IM = 0L, stringsAsFactors = FALSE
          )
        }
      }
      # PIM(M,Y) = 1 - Π (1 - PIME(Y)·MI(Y)_{d-k}), k = 1,2,3
      pime_y <- as.numeric(row$PIME)
      mi_lags_y <- c(
        mi_en_dia(mi_idx, aid, dia_anterior),
        mi_en_dia(mi_idx, aid, dia_anterior - 1L),
        mi_en_dia(mi_idx, aid, dia_anterior - 2L)
      )
      pim_my <- prob_desde_lags(pime_y, mi_lags_y)
      imy <- if (pim_my > 0) bernoulli(pim_my) else 0L
      producto_limpio <- (1 - imy)
      for (it in it_hacia[[as.character(aid)]]) {
        producto_limpio <- producto_limpio * (1 - it)
      }
      ai_nuevo <- if (producto_limpio == 1) 0L else 1L
    }

    im_agente[[as.character(aid)]] <- imy
    nuevo$AI[i] <- as.integer(ai_nuevo)
  }

  # ------------------------------------------------------------------
  # 3. Infección del medio natural alrededor de cada Y
  # ------------------------------------------------------------------
  im_medio <- list()
  for (i in seq_len(nrow(prev))) {
    row <- prev[i, ]
    aid <- as.integer(row$AID)
    mi <- 0.5 * as.numeric(row$MI)
    p_propio <- as.numeric(row$PIMS) * if (as.integer(row$AI) == 1L) 1 else 0
    iym <- bernoulli(p_propio)
    mi <- mi + iym

    for (x in ids) {
      if (x == aid) next
      clave <- paste(x, aid, sep = ":")
      dist_xy <- dist[[clave]]
      if (is.null(dist_xy)) dist_xy <- dist[[paste(aid, x, sep = ":")]]
      if (is.null(dist_xy)) next
      mi_lags_x <- c(
        mi_en_dia(mi_idx, x, dia_anterior),
        mi_en_dia(mi_idx, x, dia_anterior - 1L),
        mi_en_dia(mi_idx, x, dia_anterior - 2L)
      )
      pm_xy <- pm_ab[[clave]]
      if (is.null(pm_xy)) pm_xy <- 0.05
      pim_xy <- prob_desde_lags(pm_xy, mi_lags_x, distancia = dist_xy)
      im_xy <- if (pim_xy > 0) bernoulli(pim_xy) else 0L
      im_medio[[clave]] <- im_xy
      mi <- mi + im_xy
    }

    mi <- min(1, as.numeric(mi))
    if (mi < 0.05) mi <- 0
    nuevo$MI[i] <- round(mi, 4)
    him_rows[[length(him_rows) + 1L]] <- data.frame(
      dia = d,
      Y = aid,
      IMY = as.integer(im_agente[[as.character(aid)]]),
      IYM = as.integer(iym),
      stringsAsFactors = FALSE
    )
  }

  if (length(hit_rows) > 0) {
    for (h in seq_along(hit_rows)) {
      clave <- paste(hit_rows[[h]]$X, hit_rows[[h]]$Y, sep = ":")
      imv <- im_medio[[clave]]
      hit_rows[[h]]$IM <- if (is.null(imv)) 0L else as.integer(imv)
    }
  }
  ya <- character(0)
  if (length(hit_rows) > 0) {
    ya <- vapply(hit_rows, function(f) paste(f$X, f$Y, sep = ":"), character(1))
  }
  extra <- names(im_medio)
  for (clave in extra) {
    if (isTRUE(im_medio[[clave]] == 1L) && !(clave %in% ya)) {
      parts <- as.integer(strsplit(clave, ":", fixed = TRUE)[[1]])
      hit_rows[[length(hit_rows) + 1L]] <- data.frame(
        dia = d, X = parts[1], Y = parts[2],
        NT = 0L, IT = 0L, IM = 1L, stringsAsFactors = FALSE
      )
    }
  }

  has_rows <- data.frame(
    dia = d,
    AID = as.integer(nuevo$AID),
    AC = as.integer(nuevo$AC),
    AI = as.integer(nuevo$AI),
    MI = as.numeric(nuevo$MI),
    stringsAsFactors = FALSE
  )

  has_out <- rbind(has, has_rows)
  hit_out <- if (length(hit_rows) > 0) rbind(hit, do.call(rbind, hit_rows)) else hit
  him_out <- rbind(him, do.call(rbind, him_rows))
  rownames(nuevo) <- NULL
  rownames(has_out) <- NULL
  rownames(hit_out) <- NULL
  rownames(him_out) <- NULL
  list(agentes = nuevo, has = has_out, hit = hit_out, him = him_out)
}
