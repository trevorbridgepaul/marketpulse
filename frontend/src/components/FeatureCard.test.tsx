import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import FeatureCard from './FeatureCard'

describe('FeatureCard', () => {
  it('renders the title and description it is given', () => {
    render(
      <FeatureCard
        title="Historical Data"
        description="Query years of normalized price history."
      />,
    )

    expect(
      screen.getByRole('heading', { name: 'Historical Data' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Query years of normalized price history.'),
    ).toBeInTheDocument()
  })

  it('renders different content when given different props', () => {
    render(
      <FeatureCard
        title="Real-Time Monitoring"
        description="Stream live price updates as markets move."
      />,
    )

    expect(
      screen.getByRole('heading', { name: 'Real-Time Monitoring' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByText('Query years of normalized price history.'),
    ).not.toBeInTheDocument()
  })
})
