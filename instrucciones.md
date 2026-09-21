# Prototipo-1

Quiero hacer un modelo de simulación basada en agentes para simular como se contagian granjas de ganado porcino de la peste porcina. Quiero que escribas todo el codigo en Python usando Streamlit, y que me comentes el código para que yo pueda entenderlo. Esta es la descripción de los elementos del sistema.

Quiero una aplicación que dibuje un mapa cuadrado y ponga aleatoriamente una serie de granjas de crías de cerdos y simula como se van contagiando cuando hay un brote de una enfermedad en una de ellas.

## 1 Especificación de los parámetros del modelo

- T: El número de km del cuadrado donde se ponen las granjas (por defecto T = 10)
- Nc: Número de granjas de cria
- Ne: Número de granjas de engorde
- Nm: Número de mataderos
- N: El número total de agentes: N = Nc + Ne + Nm



## 2 Agentes del sistema

Los agentes del sistema son: 1) granjas de cria (GC), 2) granjas de engorde (GE) y 3) mataderos (MA)

Cada agente (X) tiene unas variables (entre paréntesis aparecen los valores por defecto)

- AID(X): identificador único del agente en el sistema+
- AT(X): tipo de agente: GC, GE o MA
- AX(X) y AY(X) son las coordenadas de la granja en el plano
- AN(X): Tamaño del agente. Es el número de animales en la granja, o el número de animales que puede procesar un matadero al día.
- $AI(X)_d$: estado de infección del agente, posibles valores: 0 = no, 1 = silente,  2 = declarada, 3 = en desinfección
- $AC(X)_d$: estado de cuarentena del agente: 0 = no, 1 = sí
- $MI(X)_d$: grado de infección en el medio natural en torno al agente, rango [0, 1]
- AR(X): Radio de seguridad en km alrededor del agente
- PIMS(X): Probabilidad de que el agente infecte el medio rural en un día si el agente está infectada rango [0,1],
- PIME(X): Probabilidad de que el agente se infecte de medio rural en un día si el medio está infectado, rango [0,1]
- PITS(X): Probabilidad de que el agente infecte un transporte que carga en el agente si el agente está infectado, rango [0,1]
- PITE(X): Probabilidad de que el agente se vea infectada por un transporte infectado que descarga en el agente, rango [0,1]
- DI1(X): El número de días que pasa un agente infectada silente (AI=1) hasta que se descubre la infección (AI=2),
- DI2(X): El número de días que pasa un agente desde que se declara la infección AI=2 hasta que se inicia el proceso de desinfección (AI=3)
- DI3(X): El número de días desde que se empieza la desinfección (AI=3) hasta que se elimina la infección (AI=0)

Las variables con subíndice "$_d$" pueden cambiar de un día a otro. Las otras variables se asumen fijas para el agente a lo largo de toda la simulación.

### Tabla de conexión entre agentes

Es una tabla con NxN filas y 5 columnas. Cada fila es una conexión entre dos agentes con las siguientes columnas:

- IDA: IDA del agente A
- IDB: IDA del agente B
- D es la distancia lineal en **kilómetros** entra los agentes X e Y. Se obtiene a partir de las coordenadas AX y AY de los agentes.
- V toma valores 1 o 0, dependiendo de si el agente B está dentro del radio de seguridad del agente A. M = 1 si D <= AR(A). Nótese que el agente A puede estar dentro del radio de seguridad del agente B pero no al revés necesariamente.
- M contiene el número de transportes esperado al día del agente A al agente B. puede ser un número decimal.
- PM contiene la probabilidad de que el medio del agente A infecte al medio del agente B en un día si se encuentran a 1km de distancia.

A partir de ahora, para referirme un valor de esta tabla lo denotaré con el nombre de la columnas y los nombres de los dos agentes entre paréntesis separado por una coma. Por ejemplo las conexiones entre los agentes A y B se denotan como D(A, B) para la distancia entre ellos, V(A,B) para saber si B está en el radio de seguridad de A y M(A,B) para los transportes esperados diarios de A a B y PM(A,B) para la probabilidad de infección entre medios.

Los valores M(A,B) se generan inicialmente al azar con ciertas restricciones que son:

- Si A es una granja de cría y B una granja de engorde, M(A,B) = Bernuilli(0.3) * AN/2500
- Si A es una granja de engorde y B es un matadero, M(A,B) = Bernuilli(0.3) * AN/2500
- En todas las demás situaciones M(A,B) = 0

El valor PM(A,B) se le dá por defecto el valor 0.05 para todo par de agentes.

## 4 Simulación diaria

Para cada día d, para cada agente Y se simula lo siguiente:

### Cambio de estado cuarentena

- Si en d-1 el agente Y no está en cuarentena $AC(Y)_{d-1} = 0$, entonces se revisa su estatus del siguiente modo: Si en el día anterior el agente Y, o algunos de los otros agentes que estén dentro del radio de seguridad de Y, estaban en estado de infección declarada o de desinfección, entonces el agente Y cambia su estado a cuarentena.

 $$\forall X  |  V(Y,X) = 1, \quad \exists!(AI(X)_{d-1} \in [2,3]) \Rightarrow AC(Y)_{d} = 1$$

- Si en d-1 el agente Y está en cuarentena $AC(Y)_{d-1} = 1$, entonces se revisa su estatus del siguiente modo: Si en el día anterior el agente Y, y todos los otros agentes que estén dentro del radio de seguridad de Y, estaban en estado de infección 0 o 1 (limpia o silente), entonces el agente Y cambia su estado de cuarentena a "no".

$\forall X  |  V(Y,X) = 1, \quad \nexists(AI(X)_{d-1} \in [2,3]) \Rightarrow AC(Y)_{d} = 0$

### Cambio en el estado de infección del agente Y

- Si el estado del agente en el día anterior es desinfección $AI(Y)_{d-1} = 3$ y el agente lleva en ese estado DI3(Y) días (específico para ese agente: $AI(Y)_{d-DI3(Y)} = 3$), entonces el estado se cambiará a limpio: $AI(Y)_d = 0$
- Si el estado de Y en el día anterior es infección declarada $AI(Y)_{d-1} = 2$ y el agente lleva en ese estado DI2(Y) días (específico para ese agente: $AI(Y)_{d-DI2(Y)} = 2$), entonces el estado se cambiará a desinfección $AIy_d = 3$
- Si el estado de y en el día anterior es infección silente $AI(Y)_{d-1} = 1$ y el agente lleva en ese estado DI1(Y) días (específico para ese agente: $AI(Y)_{d-DI1(Y)} = 1$), entonces el estado se cambiará a declarada $AI(Y)_d = 2$
- Si el estado de Y en el día anterior es no infección $AI(Y)_{d-1} = 0$ se simularán las infecciones recibidas de cada uno de los otros agentes (X) en el día d



#### Infección por transporte

- $IT(X,Y)_d$: Infección por transporte: Para cada agente X que el día anterior no esté en cuarentena ($AC(X)_{d-1} = 0$) y donde $M(X,Y) > 0$  se simulará los transportes que hay entre X e Y tomando una muestra al azar de una distribución de Poisson con media M(X,Y):  $T(X,Y)_d \sim Poisson(M(X,Y))$.
- Para que el agente X infecte al agente Y en UN solo transporte tienen que ocurrir tres cosas: 1) que el agente X esté infectado el día anterior $(AI(X)_{d-1} \neq 0)$, 2) que el agente X infecte el transporte en la carga (PITS(X)) y 3) que el agente Y se infecte en la descarga (PITE(Y)). Así la  probabilidad total es el producto de estas tres: $PIT1(X,Y)_d = (AI(X)_{d-1} \neq 0)*PITS(X)*PITE(Y)$.  
- L probabilidad de infectarse con alguno de estos transportes que ocurren ese día es
$PIT(X,Y)_d =1 - (1-PIT1(X,Y)_d)^{T(X,Y)_d}$.
- Después simulamos si se produjo o no infección por transporte entre esos dos agentes ese día con una muestra al azar de una distribución de Poisson con la fórmula:  $IT(X,Y)_d \sim Bernuilli(PIT(X,Y)_d)$



#### Infección del agente Y por el medio ambiente alrededor de Y

- Si el mediomabiente estaba infectado el día d-q el agente tiene una probabilidad de PIME(Y) de ser infectado en d. La probabilidad de que ese día se propague la infección del medio de Y al agente Y. Se tienen en cuenta varios días anteriores en el medio de Y:
$$PIM(M,Y)_d = 1- \left(1-PIME(Y) \cdot MI(Y)_{d-1}\right) \left(1- PIME(Y) \cdot MI(Y)_{d-2} \right) \left(1- PIME(I) \cdot MI(Y)_{d-3}\right)$$
- Simularemos el evento de infección con una Bernuilli  $IM(M,Y)_d \sim Bernuilli(PIM(M,Y)_d)$
- Finalmente, el estado de infección del agente cambia si ocurre alguna infección por medio ambiente o transporte: $AI(Y)_d = 1 - (1-IM(M,Y)_d)\prod*{X}(1-IT(X,Y)_d)$



### Cambio en el estado de infección del medio ambiente

El grado de infección en el entorno es un número entre 0 y 1

- Primero se reduce el grado de infección del entorno a la mitad cada día: $MI(Y)_d = 0.5*MI(Y)_{d-1}$
- Después se computa si hay nueva infección proveniente del propio agente Y al medio. La probabilidad de que esto ocurra es depende de PIMS(Y) y de qué Y estuviese en un estado de infección silente en el día anterior. Podemos simular esta infección muestreando con una Bernuilli: $IM(Y,M)_d \sim Bernuilli(PIMS(Y) * (AI(Y)_{d-1}==1))$ y después se la sumamos al grado estimado anteriormente: $MI(Y)_d = MI(Y)_d + IM(Y,M)_d$
- Por infección desde medio infectado de otro agente. Para cada uno de los otros agentes X, hacemos el siguiente proceso:
  1. se calcula la probabilidad de que ese día se propague la infección del medio X al medio Y. Se tienen en cuenta varios días anteriores en el medio de X:
    $$PIM(X,Y)_d = 1- \left(1-\frac{PM(X,Y) \cdot MI(X)_{d-1}}{max(1,D(B,A))}\right) \left(1-\frac{PM(X,Y) \cdot MI(X)_{d-2}}{max(1,D(B,A))}\right) \left(1-\frac{PM(X,Y) \cdot MI(X)_{d-3}}{max(1,D(B,A))} \right)$$
  2. Simulamos si se genera una infección: $IM(X,Y)_d \sim Bernuilli(PIM(X,Y)_d)$
  3. Actualizamos la infección en el medio de Y: $MI(Y)_d = MI(Y)_d + IM(X,Y)_d$
- Se limita el máximo grado de infección a 1: $MI(Y)_d = min(1, M(Y)_d)$
- Se anula infección si es menor de 0.05: $if  MI(Y)_d < 0.05 \Rightarrow MI(Y)_d=0$



## 5 Tablas Historicas para guardar resultado de las simulaciones

Los cálculos de las simulaciones diarias se guardan en varias tablas:

### Tabla de estados de los agentes

La tabla HAS recoge el estado de las variables de cada agente cada dia. Hay una fila por cada agente cada día y las variables en la tabla son: dia, AID, AC, AI, MI. Con cada día de simulación se generan tantas filas como agentes.

### Tabla de transportes e infecciones entre agentes

La tabla HIT recoge todos los transportes cada día entre cada par de agentes y las infecciones que causaron con las siguientes columnas:

- dia: dia de la simulacion
- X: AID del agente desde el que parten los transportes
- Y: AID del agente al que llegan los transportes
- NT: número de transportes de X a Y ese día = $T(X,Y)_d$
- IT: Infección por transporte entre X e Y ese día (binaria) = $IT(X,Y)_d$
- IM: Infección entre los medios de X a Y ese día (binaria) = $IM(X,Y)_d$



### Tabla de infecciones de agente con medio

La tabla HIM recoge las infecciones del medio al agente y viceversa cada dia con las siguientes columnas:

- dia: dia de la simulación
- Y: AID del agente
- IMY: Infección del medio al agente ese día (binaria) = $IM(M,Y)_d$
- IYM: Infección del agente al medio ese día (binaria) = $IM(Y,M)_d$



## 6 Especificación de la operación del sistema



### Generación aleatoria de agentes

- El usuario elige los valores de los parámetros T, Nc, Ne, Nm
- El usuario presiona el botón "generar agentes" para generar las tablas del sistema y se genera:
  - La tabla de agentes. Para las variables de localizacion (AX, AY) se les da una posición aleatoria, pero la distancia euclidiana entre dos agentes no puede ser menor a 1 km. Para el tamaño del agente (variable AN) se les da un número aleatorio se les da un número aleatorio entre 500 y 2000. Todos los agentes y sus entornos empiezan sin infección en dia 0 y sin cuarentena (AI=0, MI=0, AC=0). Los demás parámetros de los agentes se ponen a su valor por defecto según las especificaciones anteriores.
  - La matriz de distancias euclidianas entre los agentes (D).
  - La matriz de vigilancia (V) que se deduce con la matriz D y los AR(X) de los agentes
  - La matriz de transporte (M)
  - Estas matrices no se muestran en la pantalla principal.
- Se  muestran los agentes generadas aleatoriamente en el mapa. Cada tipo de agente (GC, GE, MA) se representa con un símbolo distinto y un tamaño proporcional a su tamaño. Y un color correspondiente a su estado de infección. Al pié del mapa se ve la leyenda de los símbolos y los colores



### Simulación de eventos

- El usuario deberá seleccionar una o más agentes (haciendo click con el ratón sobre el símbolo del mapa, o sobre la lista de granjas) y se cambia a "silente" el estatus de esos agentes el dia 0.
- El usuario acciona un botón de "inicio de la simulación" y a partir de aquí hay que simular que pasa cada día consecutivo en cada granja hasta que se estabilice y todas las granjas vuelvan a estar en estado limpio.
- Durante las simulaciones, tanto el mapa, como la tabla de granjas se irán actualizando.
- Se irán creando las tablas HAS, HIT y HIM que especificadas arriba según se vayan simulando días. Estas tablas no apareceran en la pantalla principal. Apareceran en otra pantalla a la que se accede a través de una pestaña que ponga "resultados de simulación". debe haver un boton junto a cada tabla que permita descargarla en formato CSV
- El programa se detendrá cuando todas las granjas estén en estado de infección de los agentes y todos los grados de infección de todos los medios naturales valgan 0: $AI(X) = 0 \quad and \quad MI(X) = 0 \quad \forall X$



## 7 Especificación de la interface

- Quiero que el interface sea un cuadro de mandos con estilo táctico militar
- El interface tendra cuatro pestañas llamadas: "Dashboard", "Agentes", "Resultados", "Análisis"
- Dentro de la pestaña "Dashboard"
  - Otro de "iniciar simulación", pausarla y reactivarla.
  - Otro botón para "reiniciar" la simulación vuelve a poner las variables AI, AC y MI de todos los agentes a 0, borra todas las tablas HAS, HIT y HIM y pone a 0 el contador de los días.
  - Mapa con las granjas representadas que se va actualizando con las simulaciones de cada día. El transporte entre dos granjas se muestra con una flecha entre ambas en el sentido del transporte. la flecha será de color naranja si ha causado una infeccion o verde si no la ha causado.
  - Debajo del mapa habrá un slide horizontal que permitirá retrotraerse a cualquier dia de la simulación y recuperar como se vería el mapa ese día.
  - Tmabién habra un boton de "play" que permita recorrer toda la secuencias de simulaciones actualizando el mapa.
- Dentro de la pestaña "Agentes"
  - Incluya primero una zona que se llame "Parametros a generar" donde se puedan definir parámetros T, Nc, Ne, y Nm, Para cada uno debe aparecer un nombre en palabras pero corto, y el simbolo entre parentesis. Junto a este pon un símbolo "?", dónde al pasar el ratón abra una pequeña leyenda explicando el significado del parámetro.
  - Incluye una sección de cuadros para incluir valores por defecto de las variables: AR=5, PIMS=0.2, PIME=0.2, PITS=0.9, PITE=0.9, DI1=3, DI2=4, DI3=15.  Pero que el usuario tambien pueda modificar estos valore spor defecto.
  - A continuación, un boton para generar datos aleatorios
  - debajo aparece la lista de agentes con las columnas de todas sus variables, las variables AID, AT, AX, AY, AN, AI, AC y MI no pueden ser modificadas por el usuario, pero las demás variables se deben poder modificar manualmente por el usuario en esta tabla. Las variables AI, AC y MI serán actualizadas por las simulaciones cada día.
  - Bajo la tabla de agentes aparece una tabla de **conexiones entre agentes**. En esta tabla el usuario puede cambiar manualmente el campo M que previamente se ha generado aleatoriamente siguiendo las reglas especificadas arriba.
  - Todas las tablas deben tener un botón que permita descargarlas en CSV
- Dentro de la pestaña de resultados se inclurirán las tablas HAS, HIT y HIM, con botones en cada una para poder ser descargarlas.
- Dentro de la pestaña de análisis aparecerá:
  - Un gráfico con los dias simulados en el eje-x y la cantidad de agentes en el eje-x.
  - Se mostrarán las series temporales a lo largo de los días de las variables: Numero de granjas cada día con a) Infeccion Silente, b) Infección declarada, c) En desinfeccion y d) en cuarentena
  - Otro gráfico con series temporales a lo largo de los días de las variables: "Numero de animales" cada día en granjas con a) Infeccion Silente, b) Infección declarada, c) En desinfeccion y d) en cuarentena
- Se pondrá una sección de cálculo de costes. En esta habra ocho cajas para introducir estimaciones de costes para:
  ```
    - CFCG = Costes fijo por dia de cuarentena grnaja
    - CACG = coste por cada animal que pasa un día en cuarentena
    - CFCM = Coste fijo por dia de cuarentena en matadero 
    - CACM = Coste por cada animal que no se mata cada dia en matadero
    - CFLG = Costes fijo por dia de limpieza granja
    - CALG = coste por cada animal que se elimina en granja
    - CFLM = Coste fijo por dia de limpieza en matadero 
    - CALM = Coste por cada animal que se limpia en matadero
  ```

Por defecto, se les puede meter unos valores de: 200€, 4€, 300€, 400€, 1000€, 10€, 600€, 15€

Debajo habrá otro gráfico con series temporales a lo largo de los días de las variables: "Costes diarios por cuarentena en granjas", "Costes diarios por cuarentena en mataderos", "Coste diarios por limpieza en granjas", "Costes diarios por limpieza en mataderos".

## 8 Codficación

- Crea el codigo relativo a la simulacion en Python y comenta bien las diferentes partes para que yo pueda entender loque vas haciendo
- La parte del código para crear el interface con el usuario lo puedes hacer del modo más efectivo

