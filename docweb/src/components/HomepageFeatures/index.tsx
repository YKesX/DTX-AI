import type {ReactNode} from 'react';
import Link from '@docusaurus/Link';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

type FeatureItem = {
  index: string;
  title: string;
  href: string;
  description: string;
  meta: string;
};

const FeatureList: FeatureItem[] = [
  {
    index: '01',
    title: 'System design',
    href: '/docs/architecture',
    description:
      'Start with the request path, service boundaries, ports, and communication model across the API, dashboard, and simulator adapter.',
    meta: 'Architecture, services, repository structure',
  },
  {
    index: '02',
    title: 'API and schemas',
    href: '/docs/api-reference',
    description:
      'Read the endpoint surface, shared models, and the validation logic that keeps replayed data and operator actions consistent.',
    meta: 'REST, WebSocket, Pydantic v2',
  },
  {
    index: '03',
    title: 'AI and operations',
    href: '/docs/ai-xai',
    description:
      'Trace how models, SHAP explanations, replay validation, and the operator workflow come together in the live dashboard.',
    meta: 'Models, XAI, metrics, workflow',
  },
];

const workflow = [
  'Ingest sensor telemetry through the FastAPI event endpoint.',
  'Run anomaly scoring and SHAP-based explanation in-process.',
  'Persist alerts, broadcast updates, and update replay metrics.',
  'Surface the result in the React dashboard for operator action.',
];

export default function HomepageFeatures(): ReactNode {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className={styles.header}>
          <p className={styles.eyebrow}>Documentation map</p>
          <Heading as="h2" className={styles.title}>
            Browse by system layer, not by template section.
          </Heading>
        </div>
        <div className={styles.grid}>
          {FeatureList.map((feature) => (
            <Link key={feature.title} className={styles.card} to={feature.href}>
              <p className={styles.index}>{feature.index}</p>
              <Heading as="h3" className={styles.cardTitle}>
                {feature.title}
              </Heading>
              <p className={styles.cardDescription}>{feature.description}</p>
              <p className={styles.cardMeta}>{feature.meta}</p>
            </Link>
          ))}
        </div>
        <div className={styles.workflowSection}>
          <div className={styles.workflowIntro}>
            <p className={styles.eyebrow}>Operational flow</p>
            <Heading as="h2" className={styles.workflowTitle}>
              The platform reads cleanly because the workflow is explicit.
            </Heading>
            <p className={styles.workflowCopy}>
              Every page in the docs folds back into the same path: telemetry
              enters, models classify, explanations justify, operators respond.
            </p>
          </div>
          <div className={styles.workflowList}>
            {workflow.map((step, idx) => (
              <article key={step} className={styles.workflowItem}>
                <span className={styles.workflowNumber}>0{idx + 1}</span>
                <p>{step}</p>
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
