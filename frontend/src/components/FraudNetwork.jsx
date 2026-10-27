import { useEffect, useRef, useState } from 'react'
import cytoscape from 'cytoscape'
import { Expand, Minus, Plus, RotateCcw } from 'lucide-react'

const COLORS = { customer: '#16998a', bank: '#59768b', wallet: '#0c88b7', merchant: '#84ad40', account: '#66758a' }
const ICONS = {
  customer: '<circle cx="12" cy="8" r="3"/><path d="M5 20v-2a7 7 0 0 1 14 0v2z"/>',
  bank: '<path d="M3 9l9-6 9 6M4 10h16M5 20h14M7 10v9m5-9v9m5-9v9"/>',
  wallet: '<rect x="3" y="6" width="18" height="14" rx="2"/><path d="M3 10h18M16 15h2"/>',
  merchant: '<path d="M4 10V5h16v5l-2 2-3-2-3 2-3-2-3 2zM6 13v7h12v-7"/>',
  account: '<circle cx="12" cy="12" r="8"/><path d="M8 12h8M12 8v8"/>',
}
const iconImage = (kind) => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${ICONS[kind] || ICONS.account}</svg>`)}`
const rupee = (x) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(x || 0)

export default function FraudNetwork({ graph, mode = 'all', search = '', expanded = false, focusAlert = null }) {
  const host = useRef(null)
  const cyRef = useRef(null)
  const [tip, setTip] = useState(null)
  const [selected, setSelected] = useState(null)
  const graphRef = useRef(graph)
  graphRef.current = graph

  useEffect(() => {
    if (!host.current) return
    const cy = cytoscape({
      container: host.current,
      elements: [],
      wheelSensitivity: 0.17,
      minZoom: 0.3,
      maxZoom: 2.7,
      style: [
        { selector: 'node', style: {
          width: 41, height: 41, shape: 'hexagon',
          'background-color': ele => COLORS[ele.data('kind')] || COLORS.account,
          'background-image': ele => iconImage(ele.data('kind')),
          'background-fit': 'contain', 'background-width': '62%', 'background-height': '62%',
          'border-width': 2, 'border-color': '#ffffff',
          label: 'data(label)', color: '#334155', 'font-size': 9, 'font-weight': 600,
          'text-valign': 'bottom', 'text-margin-y': 9, 'text-background-color': '#ffffff',
          'text-background-opacity': 0.78, 'text-background-padding': '2px'
        } },
        { selector: 'edge', style: {
          width: ele => Math.min(8, 1.3 + Math.log2(ele.data('count') + 1) * 1.4),
          'line-color': '#c6d0da', 'target-arrow-color': '#c6d0da', 'target-arrow-shape': 'triangle',
          'arrow-scale': 0.8, 'curve-style': 'bezier', opacity: 0.9,
        } },
        { selector: 'edge[scenario = "circular"], edge[scenario = "rapid"], edge[scenario = "mule"]', style: { 'line-color': '#d53b42', 'target-arrow-color': '#d53b42', width: 4.5 } },
        { selector: 'node[flagged > 0]', style: { 'border-color': '#d53b42', 'border-width': 3 } },
        { selector: '.dimmed', style: { opacity: 0.15 } },
        { selector: '.case-path', style: { opacity: 1, 'line-color': '#df6514', 'target-arrow-color': '#df6514', width: 6, 'z-index': 20 } },
        { selector: '.case-node', style: { opacity: 1, 'border-color': '#df6514', 'border-width': 5, 'z-index': 21 } },
        { selector: '.focused', style: { 'border-color': '#2563eb', 'border-width': 4, opacity: 1 } },
      ],
      layout: { name: 'preset' },
    })
    cyRef.current = cy
    const onHover = (evt) => {
      const element = evt.target
      const data = element.data()
      const pos = element.renderedMidpoint()
      setTip({ ...data, type: element.isNode() ? 'node' : 'edge', x: pos.x, y: pos.y })
    }
    const onLeave = () => setTip(null)
    const onClick = (evt) => setSelected({ ...evt.target.data(), type: evt.target.isNode() ? 'node' : 'edge' })
    cy.on('mouseover', 'node, edge', onHover)
    cy.on('mouseout', 'node, edge', onLeave)
    cy.on('tap', 'node, edge', onClick)
    cy.on('tap', event => { if (event.target === cy) setSelected(null) })
    return () => { cy.destroy(); cyRef.current = null }
  }, [])

  // Cytoscape does not always detect changes to its parent element's size.
  // Keep this one instance alive when its surrounding card becomes a fullscreen dialog.
  useEffect(() => {
    const cy = cyRef.current
    const container = host.current
    if (!cy || !container) return
    let rafId = null
    const resize = () => {
      window.cancelAnimationFrame(rafId)
      rafId = window.requestAnimationFrame(() => cy.resize())
    }
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null
    observer?.observe(container)
    resize()
    return () => { observer?.disconnect(); window.cancelAnimationFrame(rafId) }
  }, [])

  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    setTip(null)
    const rafId = window.requestAnimationFrame(() => {
      cy.resize()
      // Reframe the graph for the new canvas dimensions without regenerating nodes.
      if (cy.nodes().length) cy.fit(undefined, expanded ? 56 : 36)
    })
    return () => window.cancelAnimationFrame(rafId)
  }, [expanded])

  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    const nodes = graph?.nodes || [], edges = graph?.edges || []
    const validIds = new Set([...nodes.map(n => n.id), ...edges.map(e => e.id)])
    cy.batch(() => {
      cy.elements().forEach(el => { if (!validIds.has(el.id())) el.remove() })
      nodes.forEach((n, i) => {
        const data = { ...n, flagged: n.flagged ? 1 : 0 }
        const el = cy.getElementById(n.id)
        if (el.length) { el.data(data); return }
        const angle = i * 2.399963229728653
        const radius = 24 * Math.sqrt(i + 1)
        cy.add({ group: 'nodes', data, position: { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius } })
      })
      edges.forEach(e => {
        const data = { ...e, scenario: e.scenario || '' }
        const el = cy.getElementById(e.id)
        if (el.length) el.data(data)
        else cy.add({ group: 'edges', data })
      })
    })
    if (cy.nodes().length && !cy.scratch('_initialLayout')) {
      cy.layout({ name: 'cose', animate: false, randomize: false, fit: true, padding: 40,
        nodeRepulsion: () => 320000, idealEdgeLength: () => 160, edgeElasticity: () => 90, numIter: 240 }).run()
      cy.scratch('_initialLayout', true)
    }
    // Preserves existing node positions on incoming ticks rather than rearranging the graph.
    if (cy.nodes().length && cy.zoom() > 2.7) cy.zoom(1)
  }, [graph])

  useEffect(() => {
    const cy=cyRef.current
    if(!cy)return
    cy.elements().removeClass('case-path case-node')
    if(!focusAlert)return
    const evidence=new Set(focusAlert.transaction_ids || [])
    const accounts=new Set(focusAlert.accounts || [])
    const chosenEdges=cy.edges().filter(e => (e.data('transaction_ids') || []).some(id=>evidence.has(id)))
    const chosenNodes=cy.nodes().filter(node=>accounts.has(node.id()))
    chosenEdges.addClass('case-path')
    chosenNodes.addClass('case-node')
    if(chosenNodes.length){window.requestAnimationFrame(()=>{
      if(cyRef.current===cy)cy.fit(chosenNodes.union(chosenEdges), expanded?100:65)
    })}
  },[focusAlert,graph,expanded])

  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    const q = search.trim().toLowerCase()
    cy.elements().removeClass('dimmed focused')
    cy.edges().forEach(edge => {
      const keep = mode !== 'scenarios' || Boolean(edge.data('scenario'))
      if (!keep) edge.addClass('dimmed')
    })
    if (mode === 'scenarios') cy.nodes().forEach(node => {
      if (!node.connectedEdges().some(e => e.data('scenario'))) node.addClass('dimmed')
    })
    if (q) {
      cy.nodes().forEach(node => {
        if (node.id().toLowerCase().includes(q)) node.addClass('focused')
        else node.addClass('dimmed')
      })
    }
    if(focusAlert){
      const evidence=new Set(focusAlert.transaction_ids || [])
      cy.edges().forEach(e=>{if(!(e.data('transaction_ids')||[]).some(id=>evidence.has(id)))e.addClass('dimmed')})
      cy.nodes().forEach(n=>{if(!(focusAlert.accounts||[]).includes(n.id()))n.addClass('dimmed')})
    }
  }, [mode, search, graph, focusAlert])

  function zoom(multiplier) { const cy = cyRef.current; if (cy) cy.zoom({ level: Math.min(2.7, Math.max(0.3, cy.zoom() * multiplier)), renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } }) }
  function fit() { cyRef.current?.fit(undefined, 36) }
  function reorganize() { cyRef.current?.layout({ name: 'cose', randomize: false, animate: false, fit: true, padding: 40 }).run() }

  return <div className="network-wrap">
    <div className="network-actions" aria-label="Network graph controls">
      <button aria-label="Zoom in" title="Zoom in" onClick={() => zoom(1.25)}><Plus size={16}/></button>
      <button aria-label="Zoom out" title="Zoom out" onClick={() => zoom(.8)}><Minus size={16}/></button>
      <button aria-label="Fit all nodes" title="Fit graph to view" onClick={fit}><Expand size={16}/></button>
      <button aria-label="Rearrange graph" title="Rearrange nodes" onClick={reorganize}><RotateCcw size={15}/></button>
    </div>
    <div ref={host} className="network-stage" role="img" aria-label="Interactive account transaction network; click an account or transfer for details"/>
    {!graph?.nodes?.length && <div className="graph-empty">No graph data yet. Import a CSV or start the synthetic transaction simulation.</div>}
    {tip && <div className="node-tooltip" style={{ left: Math.max(12, tip.x + 16), top: Math.max(12, tip.y - 20) }}>
      <strong>{tip.type === 'node' ? tip.id : `${tip.source} → ${tip.target}`}</strong>
      {tip.type === 'node' ? <><span>Type: {tip.kind}</span><span>Incoming: {tip.incoming} · Outgoing: {tip.outgoing}</span><span>Received: {rupee(tip.received)}</span><span>Sent: {rupee(tip.sent)}</span></>
        : <><span>Transfers: {tip.count}</span><span>Value: {rupee(tip.amount)}</span><span>{tip.scenario ? `ML alert: ${tip.scenario} · risk ${tip.risk_score}/100` : 'No ML alert attached'}</span></>}
    </div>}
    {selected && <div className="network-selection"><button className="selection-close" onClick={() => setSelected(null)} aria-label="Close account details">×</button><strong>{selected.type === 'node' ? selected.id : `${selected.source} → ${selected.target}`}</strong><p>{selected.type === 'node' ? `Account type: ${selected.kind} · Incoming ${selected.incoming} · Outgoing ${selected.outgoing}` : `${selected.count} transactions · ${rupee(selected.amount)}`}</p><small>Sample data · Derived from stored transactions</small></div>}
  </div>
}
