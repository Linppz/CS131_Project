**Team Number:** 

21

**Team Members:**

* **Ryan Yang** (ryang097)  
* **Pengzhen Lin** (ID: 862425101\)



---

# **Cold-Chain / Medical Storage Monitoring System**

---

## **Use Case**

Cold-chain storage is critical in the **healthcare and food logistics industries**, where products such as vaccines, insulin, biologics, and perishable foods must be maintained within strict temperature ranges to remain safe and effective. Even short temperature excursions—caused by door openings, cooling system degradation, power loss, or network outages—can lead to irreversible spoilage without immediate detection.

Many existing cold-chain monitoring solutions rely on **cloud-based processing and simple threshold alarms**, which introduces several limitations:

* Increased response latency due to network round trips

* System failure during internet outages

* High false-alarm rates caused by brief or non-critical temperature fluctuations

* Limited ability to detect unsafe trends before damage occurs

This project addresses these limitations by designing a **fault-tolerant edge computing system** that performs real-time sensing and decision-making directly at the edge, while still leveraging the cloud for long-term analytics and compliance reporting. Key challenges include maintaining reliable operation during network outages, detecting unsafe temperature trends early rather than reacting only to failures, and minimizing false alarms without compromising safety.

---

## **Solution (Full-Scale System)**

The full-scale solution is a **distributed edge–fog–cloud cold-chain monitoring platform** designed to support multiple cold-storage units across a facility. Each storage unit is equipped with a low-power sensor edge device that continuously collects environmental data, including temperature and door-open indicators. A second edge computing device performs real-time analytics to estimate spoilage risk based on **temperature trends, rate of change, and cumulative exposure duration**, rather than fixed thresholds alone.

A fog computing layer manages communication between devices, enforces alert escalation policies, and buffers data during internet outages to ensure uninterrupted system operation. Cloud services aggregate historical data across storage units to enable predictive modeling, regulatory compliance reporting, and proactive maintenance insights. The system is explicitly designed so that **all safety-critical decisions occur locally at the edge**, while the cloud is used only for non-time-critical analytics and optimization.

---

## **Demo (Proof of Concept)**

The demo implements a **single cold-storage unit** using an insulated container to simulate medical or food storage conditions. Temperature and light sensors capture environmental changes, including simulated door-open events. A local analytics edge node processes this data in real time to compute a spoilage risk level and trigger alerts when unsafe trends are detected.

The demo will demonstrate:

* Real-time sensor data acquisition and local edge analytics

* Interaction between two edge devices (sensor node and analytics node)

* Visual and audible alerts based on computed risk level

* A local fog-hosted dashboard displaying system state

* Cloud-based data logging and simple predictive feedback

To demonstrate fault tolerance and justify the edge-first design, internet connectivity will be intentionally disrupted while showing that monitoring and alerting continue locally. Buffered data will be synchronized to the cloud once connectivity is restored.

---

## **Task Distribution (Layer Responsibilities)**

### **Edge Device 1 – Sensor Node (Arduino)**

This device is responsible for **data sensing and immediate local processing**. It continuously collects temperature and light measurements at fixed intervals and publishes raw sensor data to the analytics edge device. The sensor node also enforces hard safety limits by triggering immediate alerts if absolute temperature thresholds are exceeded. Its design prioritizes reliability, low power consumption, and independence from cloud connectivity.

---

### **Edge Device 2 – Analytics Node (Jetson Nano)**

This device performs **edge-level decision-making and analytics**. It subscribes to raw sensor data from the Arduino and performs real-time processing, including noise smoothing, temperature trend analysis, and cumulative exposure tracking. Based on this analysis, it computes a spoilage risk level (e.g., LOW, MEDIUM, HIGH) and generates structured warning events. All time-critical decisions—such as identifying unsafe trends and escalating risk—occur at this layer to minimize latency and reduce false alarms.

---

### **Fog Layer – Local Manager (PC/Laptop)**

The fog device manages **intermediate device coordination and system reliability**. It aggregates alerts from the analytics edge device, applies alert escalation policies, and hosts a local monitoring dashboard. During network outages, the fog layer buffers sensor data and alerts, ensuring uninterrupted operation and eventual synchronization with the cloud. It also serves as the controlled gateway between the edge system and cloud services.

---

### **Cloud Service**

The cloud component is responsible for **non-critical computation and long-term analytics**. It stores historical sensor and alert data, performs trend analysis and predictive modeling (e.g., estimating remaining safe storage time), and supports compliance reporting and auditing. Cloud services are not required for immediate system operation and are used only for analytics, reporting, and optimization.

---

