import type {ReactNode} from 'react';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import HomepageFeatures from '@site/src/components/HomepageFeatures';
import Heading from '@theme/Heading';

import styles from './index.module.css';

const signalCards = [
  {
    value: '4',
    label: 'Model families',
    detail: 'LightGBM, XGBoost, Random Forest, LSTM-AE',
  },
  {
    value: 'Live',
    label: 'Operator feedback loop',
    detail: 'WebSocket updates, acknowledgement, escalation, resolution',
  },
  {
    value: 'SHAP',
    label: 'Explainability layer',
    detail: 'Per-feature reasoning attached to every alert',
  },
];

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <header className={styles.heroBanner}>
      <div className={styles.heroInner}>
        <div className={styles.heroCopy}>
          <p className={styles.heroEyebrow}>Documentation / Spring 2026</p>
          <Heading as="h1" className={styles.heroTitle}>
            {siteConfig.title}
          </Heading>
          <p className={styles.heroSubtitle}>{siteConfig.tagline}</p>
          <p className={styles.heroDescription}>
            A compact reference for the smart warehouse platform: anomaly
            detection, explainable AI, operator workflows, and the full stack
            behind the demo environment.
          </p>
          <div className={styles.buttons}>
            <Link className="button button--primary button--lg" to="/docs/overview">
              Read the overview
            </Link>
            <Link className="button button--secondary button--lg" to="/docs/architecture">
              Explore architecture
            </Link>
          </div>
          <div className={styles.heroMeta}>
            <span>Version 0.2.0</span>
            <span>Graduation project</span>
            <span>Atılım University</span>
          </div>
        </div>
        <div className={styles.heroPanel}>
          <p className={styles.panelLabel}>System flow</p>
          <div className={styles.pipeline}>
            <span>Sensor event</span>
            <span>FastAPI</span>
            <span>AI pipeline</span>
            <span>Dashboard</span>
          </div>
          <p className={styles.panelText}>
            Real-time telemetry enters the API, is classified by the anomaly
            pipeline, explained with SHAP, persisted to SQLite, and broadcast to
            the React dashboard.
          </p>
          <Link className={styles.inlineLink} to="/docs/services">
            View service boundaries
          </Link>
        </div>
      </div>
    </header>
  );
}

function SignalSection() {
  return (
    <section className={styles.signalSection}>
      <div className="container">
        <div className={styles.sectionHeading}>
          <p className={styles.sectionEyebrow}>At a glance</p>
          <Heading as="h2" className={styles.sectionTitle}>
            A documentation surface built for fast scanning.
          </Heading>
        </div>
        <div className={styles.signalGrid}>
          {signalCards.map((card) => (
            <article key={card.label} className={styles.signalCard}>
              <p className={styles.signalValue}>{card.value}</p>
              <Heading as="h3" className={styles.signalLabel}>
                {card.label}
              </Heading>
              <p className={styles.signalDetail}>{card.detail}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

export default function Home(): ReactNode {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout
      title={`${siteConfig.title} Documentation`}
      description="Minimal documentation site for the DTX-AI anomaly detection platform.">
      <HomepageHeader />
      <main className={styles.homeMain}>
        <SignalSection />
        <HomepageFeatures />
      </main>
    </Layout>
  );
}
