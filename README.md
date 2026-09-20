# MicroPay — Microservicios Orquestados en AWS

Proyecto de arquitectura cloud desarrollado como Evaluación del Módulo 7 del
Bootcamp de Arquitectura Cloud (SOFOFA). Diseña e implementa la migración de un
sistema monolítico a una arquitectura de microservicios orquestados en AWS,
usando exclusivamente recursos disponibles en AWS Academy Learner Lab.

## Contexto del caso

**Unidad solicitante:** Departamento de Tecnología de la fintech MicroPay.

El sistema monolítico actual de MicroPay impide liberar funcionalidades de
forma ágil y presenta cuellos de botella durante picos de uso. Este proyecto
diseña una arquitectura basada en microservicios que aplica buenas prácticas
de escalabilidad, disponibilidad y desacoplamiento.

## Arquitectura — resumen

El sistema se descompone en dos microservicios independientes (**Usuarios** y
**Pagos**), cada uno contenerizado en Docker, publicado en su propio
repositorio de Amazon ECR, y desplegado como un Service independiente en un
clúster de Amazon ECS con Fargate, con Auto Scaling activo basado en CPU.

La VPC se distribuye en dos Availability Zones. Sus tareas de ECS Fargate y
los nodos de cada Application Load Balancer (**interno**, sin IP pública)
corren en las subredes privadas de esas AZ, con un NAT Gateway propio por
zona (y un único Internet Gateway a nivel de VPC) usado solo para la salida
a internet de las tareas, el tráfico de solicitudes nunca sale a internet,
viaja enteramente dentro de la VPC vía VPC Link. Ambos microservicios se
exponen al exterior a través de un único **Amazon API Gateway (HTTP API)**,
con rutas diferenciadas:

- `https://<api-id>.execute-api.<region>.amazonaws.com/usuarios`
- `https://<api-id>.execute-api.<region>.amazonaws.com/pagos`

El monitoreo se centraliza en Amazon CloudWatch: logs de aplicación por
servicio, logs de acceso de cada ALB hacia S3, y una alarma de CPU conectada
a SNS que evidencia el comportamiento del Auto Scaling.

📄 El diagrama completo está en [`diagrams/export/`](./diagrams/export/).

### Componentes principales

| Componente | Servicio AWS | Rol |
|---|---|---|
| Punto único de entrada | Amazon API Gateway (HTTP API) | Enrutamiento externo por path (`/usuarios`, `/pagos`) |
| Conectividad de la VPC | Internet Gateway | Única salida a internet de la VPC, usada solo por los NAT Gateway |
| Conectividad privada | VPC Link | Conecta API Gateway con los ALB internos sin exponerlos a internet |
| Balanceo por servicio | 2x Application Load Balancer (interno) | Uno por microservicio, desplegado en 2 AZ, sin punto único de falla compartido |
| Cómputo | Amazon ECS (Fargate) | Ejecuta las tareas de cada microservicio, con Auto Scaling (2-4) |
| Registro de imágenes | Amazon ECR | Un repositorio por microservicio |
| Salida a internet (tareas) | 2x NAT Gateway (uno por AZ) | Permite a las tareas hacer *pull* de imágenes desde ECR |
| Observabilidad | CloudWatch (Logs, Alarms), SNS, S3 | Logs por servicio, logs de acceso del ALB, alarma de CPU |

## Microservicios

| Servicio | Responsabilidad | Ruta expuesta |
|---|---|---|
| `usuarios` | Gestión de identidad y datos de cuenta | `/usuarios` |
| `pagos` | Procesamiento y consulta de transacciones | `/pagos` |

Ver [`services/usuarios/README.md`](./services/usuarios/README.md) y
[`services/pagos/README.md`](./services/pagos/README.md) para el detalle de
cada uno.

## Decisiones de arquitectura (ADR)

| ADR | Decisión |
|---|---|
| [0001](./adr/0001-descomposicion-microservicios.md) | Descomposición del dominio en microservicios |
| [0002](./adr/0002-plataforma-computo-contenedores.md) | Plataforma de cómputo (ECS Fargate + Auto Scaling) |
| [0003](./adr/0003-registro-imagenes-ecr.md) | Estrategia de registro de imágenes (Amazon ECR) |
| [0004](./adr/0004-exposicion-conectividad-api-gateway.md) | Exposición y conectividad vía API Gateway |
| [0005](./adr/0005-monitoreo-logging-cloudwatch.md) | Monitoreo y logging con CloudWatch |

## Estructura del repositorio

```
micropay-microservicios-aws/
├── README.md
├── docs/
│   └── arquitectura-general.md
├── adr/
├── diagrams/
│   ├── src/
│   └── export/
└── services/
    ├── usuarios/
    └── pagos/
```

## Cómo se despliega (visión de alto nivel)

1. **Red base:** VPC con 2 Availability Zones, un Internet Gateway
   adjunto a la VPC, y en cada AZ una subred pública (NAT Gateway) y una
   subred privada (tareas de Fargate y nodos del ALB interno); cada subred
   privada enruta hacia el NAT Gateway de su propia AZ. *(ADR-0004)*
2. **Imágenes de contenedor:** Build local de cada microservicio con
   Docker y push manual a su repositorio en Amazon ECR, etiquetado por
   commit. *(ADR-0003)*
3. **Cómputo:** Clúster de Amazon ECS (Fargate) con una Task Definition y
   un Service por microservicio, usando `LabRole` y Auto Scaling basado en
   CPU (mín. 2, máx. 4 tareas). *(ADR-0002)*
4. **Balanceo:** Un Application Load Balancer interno por microservicio,
   desplegado en ambas subredes privadas (multi-AZ), con su target group
   apuntando a las tareas Fargate en esas mismas subredes. *(ADR-0004)*
5. **Entrada única:** Amazon API Gateway (HTTP API) con un VPC Link hacia
   cada ALB interno, y rutas `/usuarios/{proxy+}` y `/pagos/{proxy+}`.
   *(ADR-0004)*
6. **Observabilidad:** Log groups de CloudWatch por servicio, logs de
   acceso de cada ALB hacia S3, y alarma de CPU conectada a un tópico SNS.
   *(ADR-0005)*
7. **Validación:** Llamadas HTTP a cada ruta expuesta por API Gateway y
   revisión de logs en CloudWatch.

Cada paso se ejecuta y valida manualmente desde la consola de AWS Academy
Learner Lab; no hay automatización de infraestructura como código en el
alcance de esta evaluación.

## Restricciones del entorno

- No es posible crear roles IAM personalizados, se usa `LabRole`.
- No hay acceso SSH a instancias, no aplica al usar Fargate.
- Los recursos se eliminan al finalizar cada sesión de laboratorio; las
  decisiones de dimensionamiento asumen un entorno temporal.

## Estado del proyecto

🚧 En desarrollo - Módulo 7 del Bootcamp de Arquitectura Cloud (SOFOFA).

## Autor

**Fidel Vera** - [github.com/fevc08](https://github.com/fevc08)