# Arquitectura General: MicroPay Microservicios Orquestados

## 1. Resumen ejecutivo

MicroPay migra su sistema monolítico a una arquitectura de microservicios
desplegada en AWS Academy Learner Lab. La arquitectura descompone el dominio
en dos servicios independientes (Usuarios y Pagos), cada uno contenerizado y
orquestado con Amazon ECS Fargate, expuestos a través de un único punto de
entrada (Amazon API Gateway) y observados de forma centralizada con Amazon
CloudWatch. Todas las decisiones de diseño están documentadas como ADR en
[`/adr`](../adr/).

## 2. Objetivos de la arquitectura

Derivados directamente de la consigna de la evaluación:

| Objetivo | Cómo se resuelve |
|---|---|
| Escalabilidad | Auto Scaling por servicio basado en CPU (ADR-0002) |
| Disponibilidad | ALB interno por servicio en 2 AZ, Auto Scaling con mínimo 1 tarea por AZ (ADR-0002, ADR-0004) |
| Desacoplamiento | Bounded contexts independientes, sin base de datos ni lógica compartida, comunicación solo vía HTTP a través del Gateway (ADR-0001) |

## 3. Vista lógica

Dos microservicios, cada uno dueño de su propio dominio de negocio:

- **Usuarios:** gestión de identidad y datos de cuenta.
- **Pagos:** procesamiento y consulta de transacciones.

No existe comunicación directa entre ambos microservicios en esta iteración;
cada uno es consumido de forma independiente por el cliente externo a través
del API Gateway. Esta es una decisión deliberada de alcance (ver ADR-0001),
no una limitación técnica.

## 4. Vista de despliegue

La arquitectura se distribuye en una VPC con **dos Availability Zones**
(`us-east-1a`, `us-east-1b`), no por preferencia de disponibilidad, sino
porque un Application Load Balancer no puede aprovisionarse con subredes de
una sola AZ.

**Internet Gateway:**
- Uno solo, adjunto a la VPC (no a una AZ específica). Provee la única ruta
  de entrada/salida hacia internet, usada exclusivamente por los NAT
  Gateway, el tráfico de solicitudes de los clientes nunca pasa por aquí.

**Subred pública (por AZ):**
- Un NAT Gateway propio de la AZ, cuya tabla de rutas apunta al Internet
  Gateway. Es el único componente en esta subred.

**Subred privada (por AZ):**
- Tareas de ECS Fargate de ambos microservicios, con al menos 1 tarea por
  AZ y por servicio como piso (ADR-0002).
- Nodos de ambos Application Load Balancers, configurados como **internos**
  (`scheme: internal`, sin IP pública), solo alcanzables desde las ENIs que
  crea el VPC Link dentro de la misma VPC. Su tabla de rutas apunta al NAT
  Gateway de su propia AZ, usado únicamente para que las tareas hagan *pull*
  de imágenes desde ECR, nunca para el tráfico de solicitudes.

**Fuera de la VPC:**
- Amazon API Gateway (HTTP API) con VPC Link independiente por servicio.
- Dos repositorios de Amazon ECR.
- Log groups de CloudWatch por servicio, alarma de CPU + SNS.
- Bucket S3 para logs de acceso de ambos ALB.

Esta descripción es la base para el diagrama de arquitectura (ver
`diagrams/`), que representa visualmente estos mismos componentes y sus
conexiones.

## 5. Flujo de una solicitud

Ejemplo: una llamada externa a `GET /usuarios/123`.

1. El cliente envía la solicitud a la URL pública del API Gateway.
2. API Gateway resuelve la ruta `/usuarios/{proxy+}` y la reenvía a través
   del VPC Link asociado a Usuarios.
3. El VPC Link entrega la solicitud, mediante sus ENIs privadas dentro de la
   VPC, al Application Load Balancer **interno** del microservicio Usuarios,
   ubicado en subred privada, sin salir en ningún momento hacia internet.
4. El ALB evalúa el health check de sus targets (distribuidos en ambas AZ) y
   enruta la solicitud a una tarea saludable de ECS Fargate.
5. La tarea procesa la solicitud y responde al ALB, que a su vez responde al
   VPC Link y este a API Gateway.
6. API Gateway devuelve la respuesta final al cliente.
7. En paralelo, la tarea escribe su log de aplicación en
   `/ecs/micropay/usuarios` (CloudWatch Logs), y el ALB registra la solicitud
   en su log de acceso hacia S3.

El flujo para `/pagos` es idéntico, pero completamente aislado: usa su propio
VPC Link, su propio ALB interno y sus propias tareas — en ningún punto
comparte infraestructura de cómputo o de red con Usuarios más allá de la VPC
y el API Gateway compartido como fachada.

## 6. Atributos de calidad y su trazabilidad

| Atributo | Decisión de diseño | ADR |
|---|---|---|
| Escalabilidad | Auto Scaling por servicio (target tracking sobre CPU, 2-4 tareas) | ADR-0002 |
| Disponibilidad | ALB interno por servicio desplegado en 2 AZ; NAT Gateway por AZ; mínimo 1 tarea por AZ | ADR-0002, ADR-0004 |
| Desacoplamiento | Descomposición por bounded context; repositorios ECR y ciclos de despliegue independientes | ADR-0001, ADR-0003 |
| Seguridad | ALB interno sin IP pública, alcanzable solo desde el VPC Link; tareas en subred privada; Security Groups por capa | ADR-0004 |
| Observabilidad | Logs por servicio, logs de acceso del ALB, alarma de CPU con notificación SNS | ADR-0005 |

## 7. Supuestos y límites de alcance

- No hay persistencia de datos en esta iteración (sin base de datos por
  servicio), ver brecha documentada en ADR-0001.
- No hay comunicación asíncrona entre microservicios (sin SNS/SQS de
  integración), el único uso de SNS en este proyecto es para la alarma de
  CPU (ADR-0005), no para mensajería entre servicios.
- No hay pipeline de CI/CD; el build y push de imágenes es manual desde
  Docker CLI local (ADR-0003).
- Todos los recursos se destruyen al finalizar la sesión de Learner Lab; las
  decisiones de dimensionamiento asumen un entorno temporal, no productivo.

## 8. Referencias

Ver el detalle completo de cada decisión, sus alternativas consideradas y su
alineación con AWS Well-Architected Framework en [`/adr`](../adr/).