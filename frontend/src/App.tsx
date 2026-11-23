import FeatureCard from './components/FeatureCard'
import './App.css'

const features = [
  {
    title: 'Historical Data',
    description:
      'Query years of normalized daily and intraday price history, stored reliably in PostgreSQL.',
  },
  {
    title: 'Real-Time Monitoring',
    description:
      'Stream live price updates as markets move, without sacrificing data integrity.',
  },
  {
    title: 'Financial Analytics',
    description:
      'Turn raw market data into interactive, explainable analytics you can trust.',
  },
]

function App() {
  return (
    <div className="page">
      <header className="hero">
        <span className="brand">MarketPulse</span>
        <h1>Market data analytics, built for clarity.</h1>
        <p className="tagline">
          MarketPulse ingests historical and real-time stock market data,
          stores it reliably, and turns it into interactive analytics you can
          trust.
        </p>
      </header>

      <section className="features" aria-label="Platform features">
        {features.map((feature) => (
          <FeatureCard
            key={feature.title}
            title={feature.title}
            description={feature.description}
          />
        ))}
      </section>
    </div>
  )
}

export default App
