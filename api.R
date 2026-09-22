# api.R
# API Plumber: integra R_src/*.R con source() y expone /simular.
#
# Arranque (desde la raiz del proyecto):
#   Rscript -e 'plumber::plumb("api.R")$run(host="0.0.0.0", port=8000)'
#
# El front R_Java se sirve en /  (index.html, css/, js/).

Sys.setlocale("LC_ALL", "en_US.UTF-8")

this_dir <- tryCatch({
  dirname(normalizePath(sys.frame(1)$ofile))
}, error = function(e) {
  getwd()
})
if (!file.exists(file.path(this_dir, "R_src", "agente.R"))) {
  this_dir <- getwd()
}

source(file.path(this_dir, "R_src", "agente.R"), encoding = "UTF-8")
source(file.path(this_dir, "R_src", "ciclo.R"), encoding = "UTF-8")
source(file.path(this_dir, "R_src", "experimento.R"), encoding = "UTF-8")
source(file.path(this_dir, "R_src", "analitica.R"), encoding = "UTF-8")

java_r_dir <- file.path(this_dir, "R_Java")


leer_cuerpo <- function(req) {
  raw <- req$postBody
  if (is.null(raw) || !nzchar(raw)) return(list())
  jsonlite::fromJSON(raw, simplifyVector = TRUE)
}


#* @filter cors
function(req, res) {
  res$setHeader("Access-Control-Allow-Origin", "*")
  res$setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
  res$setHeader("Access-Control-Allow-Headers", "Content-Type")
  if (identical(req$REQUEST_METHOD, "OPTIONS")) {
    res$status <- 200
    return(list(ok = TRUE))
  }
  plumber::forward()
}


#* Salud de la API
#* @get /salud
#* @serializer json list(auto_unbox = TRUE)
function() {
  list(ok = TRUE, servicio = "SIA-ADO", motor = "R")
}


#* Parámetros y costes por defecto
#* @get /defaults
#* @serializer json list(auto_unbox = TRUE)
function() {
  list(params = valores_por_defecto(), costes = costes_por_defecto())
}


#* Genera el teatro (agentes + conexiones) sin simular
#* @post /generar
#* @serializer json list(auto_unbox = TRUE, na = "null")
function(req, res) {
  body <- tryCatch(leer_cuerpo(req), error = function(e) {
    res$status <- 400
    return(list(error = e$message))
  })
  if (!is.null(body$error)) return(body)
  resultado <- tryCatch({
    teatro <- crear_teatro(body)
    list(
      params = teatro$params,
      agentes = teatro$agentes,
      conexiones = teatro$conexiones
    )
  }, error = function(e) {
    res$status <- 400
    list(error = e$message)
  })
  resultado
}


#* Ejecuta la simulación completa y devuelve estadísticas finales en JSON
#* @post /simular
#* @serializer json list(auto_unbox = TRUE, na = "null")
function(req, res) {
  body <- tryCatch(leer_cuerpo(req), error = function(e) {
    res$status <- 400
    return(list(error = paste("JSON inválido:", e$message)))
  })
  if (!is.null(body$error)) return(body)

  resultado <- tryCatch({
    params <- mezclar_params(body)
    costes <- mezclar_costes(body$costes)
    brotes <- integer(0)
    if (!is.null(body$brotes)) brotes <- as.integer(unlist(body$brotes))
    agentes <- as_agentes_df(body$agentes)
    conexiones <- as_conexiones_df(body$conexiones)
    teatro <- ejecutar_experimento(
      params = params,
      brotes = brotes,
      agentes = agentes,
      conexiones = conexiones,
      costes = costes
    )
    resumen_estadistico(teatro)
  }, error = function(e) {
    res$status <- 400
    list(error = e$message)
  })
  resultado
}


#* Front-end R_Java
#* @get /
function(res) {
  html <- file.path(java_r_dir, "index.html")
  if (!file.exists(html)) {
    res$status <- 404
    return("R_Java/index.html no encontrado")
  }
  plumber::include_file(html, res, content_type = "text/html; charset=utf-8")
}


#* @assets ./R_Java/css /css
list()

#* @assets ./R_Java/js /js
list()
