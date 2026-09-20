# ADR-0004: Patrón de exposición y conectividad vía API Gateway

## Estado
Aceptada, 17 de septiembre de 2026

## Contexto
Los microservicios Usuarios y Pagos corren como tareas de ECS Fargate dentro
de una VPC (ADR-0002). La consigna exige un **punto único de entrada** para
el sistema, con rutas diferenciadas por servicio (`/usuarios`, `/pagos`),
validable mediante llamadas HTTP externas.

Se deben resolver dos decisiones relacionadas:
1. Qué tipo de Amazon API Gateway usar como fachada pública.
2. Cómo conecta ese API Gateway con las tareas de Fargate, que viven en
   subredes privadas y no son directamente alcanzables desde internet.

## Decisión

### 1. Tipo de API Gateway
Se usa **API Gateway HTTP API** (no REST API), por ser más simple de
configurar, más económico y suficiente para el alcance de este proyecto.

### 2. Conectividad hacia ECS Fargate
La VPC se distribuye en **dos Availability Zones** (`us-east-1a`,
`us-east-1b`).

- **Internet Gateway**: uno solo, adjunto a la VPC, provee la única ruta
  de entrada/salida hacia internet para toda la VPC.
- **Subred pública por AZ**: aloja únicamente el NAT Gateway de esa zona,
  cuya tabla de rutas apunta al Internet Gateway.
- **Subred privada por AZ**: aloja las tareas de Fargate **y los nodos del
  ALB interno** de ambos microservicios. Su tabla de rutas apunta al NAT
  Gateway de su propia AZ, usado únicamente para que las tareas hagan
  *pull* de imágenes desde ECR, nunca para el tráfico de solicitudes.
- **Ambos Application Load Balancers se configuran como internos**
  (`scheme: internal`), sin IP pública. Solo son alcanzables desde las ENIs
  que crea el VPC Link dentro de la misma VPC.
- Cada ALB se aprovisiona con ambas subredes privadas (1a y 1b), y cada ECS
  Service registra tareas en esas mismas subredes, garantizando al menos un
  target saludable por AZ (ver ADR-0002).

### 3. Enrutamiento
El VPC Link crea sus propias ENIs en las subredes privadas, con su propio
Security Group. Se definen dos rutas en el HTTP API:

| Ruta | Método | Integración |
|---|---|---|
| `/usuarios/{proxy+}` | ANY | VPC Link → ALB interno (target group de Usuarios) |
| `/pagos/{proxy+}` | ANY | VPC Link → ALB interno (target group de Pagos) |

El uso de `{proxy+}` permite que cada microservicio maneje sus propias
subrutas internas sin declarar cada endpoint individualmente.

**Security Groups:**
- **ALB interno**: permite tráfico entrante solo desde el Security Group
  del VPC Link.
- **Tareas ECS**: permiten tráfico entrante solo desde el Security Group
  del ALB correspondiente.

Con este diseño, el tráfico de un cliente externo viaja API Gateway → VPC
Link (ENI privada) → ALB interno → tarea Fargate, en su totalidad dentro de
la red de AWS, sin tocar nunca el Internet Gateway ni el NAT Gateway.

## Alternativas consideradas

| Alternativa | Por qué se descarta |
|---|---|
| API Gateway REST API | Mayor complejidad de configuración sin aportar capacidades necesarias para este proyecto |
| Tareas de Fargate con IP pública directa, sin ALB ni VPC Link | Las IPs públicas de tareas Fargate cambian en cada reemplazo, rompiendo la integración |
| Integración HTTP pública directa hacia un ALB público (sin VPC Link) | Expone el ALB directamente a internet, ampliando la superficie de ataque |
| Un solo ALB compartido con listener rules por path | Convierte al ALB en punto único de falla compartido por ambos microservicios, contradiciendo ADR-0001 |
| NAT Gateway único compartido entre ambas AZ | Introduce dependencia cruzada: si la AZ del único NAT Gateway falla, la otra AZ pierde salida a internet |
| ALB internet-facing en subred pública (versión anterior de este ADR) | El ALB obtendría IP pública y sería alcanzable directamente por su DNS, sin pasar por API Gateway, contradice el objetivo de punto único de entrada |

## Consecuencias

**Positivas**
- El ALB resuelve el problema de IPs dinámicas de las tareas Fargate.
- El ALB interno no tiene IP pública: es físicamente inalcanzable desde
  fuera de la VPC, la única vía de acceso es el VPC Link.
- El patrón `{proxy+}` evita mapear manualmente cada endpoint interno.
- Aislamiento de disponibilidad entre servicios: un ALB por microservicio
  evita que ambos compartan el mismo punto único de falla.
- Las tareas de Fargate quedan completamente inalcanzables desde internet.

**Negativas / trade-offs**
- Se introducen varios componentes de red (2 ALB, 2 VPC Link, 2 NAT
  Gateway, 1 Internet Gateway) entre el cliente y el microservicio.
- El VPC Link tiene costo por hora de aprovisionamiento, independiente del
  tráfico.
- Los NAT Gateway (uno por AZ) son de los componentes más costosos de esta
  arquitectura.

## Alineación con AWS Well-Architected Framework
- **Security**: las tareas y los ALB (internos, sin IP pública) operan en
  subredes privadas sin exposición a internet; el VPC Link es el único
  camino hacia el ALB, defensa en profundidad de principio a fin (API
  Gateway → VPC Link → ALB interno → tarea privada).
- **Reliability**: el ALB actúa como capa de indirección estable frente a
  los cambios de IP de las tareas, y opera en 2 AZ.
- **Performance Efficiency**: HTTP API tiene menor latencia que REST API
  para este caso de uso de simple proxy.
- **Cost Optimization**: HTTP API es más económico que REST API por millón
  de solicitudes.

## Brecha entre diseño ideal y AWS Academy Learner Lab
- **Ideal**: además del patrón multi-AZ y del ALB interno ya implementados,
  un diseño de producción añadiría AWS WAF delante de API Gateway y VPC
  Endpoints para que las tareas alcancen ECR sin depender del NAT Gateway.
- **Esta iteración**: se implementa el patrón completo de aislamiento de
  red (multi-AZ, ALB interno, NAT Gateway por AZ) por ser requisitos
  técnicos y de seguridad centrales al objetivo de la evaluación. WAF y VPC
  Endpoints quedan fuera de alcance por no ser exigidos.
- No se identifican bloqueos adicionales de IAM más allá de `LabRole`.

## RTO/RPO objetivo
- **RTO**: < 5 minutos, el ALB deja de enviar tráfico a una tarea no
  saludable, y al operar en 2 AZ, también deja de enrutar hacia una AZ
  degradada.
- **RPO**: No aplica, no hay estado persistente en el camino de la
  solicitud.

## Costo
- **HTTP API**: por millón de solicitudes, sin costo fijo por hora.
- **VPC Link**: costo por hora de aprovisionamiento (uno por servicio).
- **ALB**: costo por hora más LCU consumida, cada ALB opera en 2 AZ (el
  costo no varía por ser interno vs. internet-facing).
- **NAT Gateway**: costo por hora más GB procesado, uno por AZ (2 total).
Este es el ADR con mayor impacto de costo del proyecto; eliminar estos
recursos apenas se cierre la sesión de laboratorio.

## Referencias
- Amazon API Gateway - HTTP APIs
- Amazon API Gateway - Private integrations for HTTP APIs (VPC Links V2)
- Elastic Load Balancing - Application Load Balancer