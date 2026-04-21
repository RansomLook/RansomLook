document.addEventListener('DOMContentLoaded', () => {
  const el = document.getElementById('graph-data');
  const container = document.getElementById('cy-container');
  if (!el || !container) return;

  const data = JSON.parse(el.textContent);
  const colorFor = RL.colorFor;

  const elements = [];

  // Center node (the actor)
  elements.push({
    data: { id: data.center, label: data.center, type: 'actor-self' },
  });

  // Helper to add a related node + edge
  const add = (name, type, known) => {
    const id = type + ':' + name;
    elements.push({ data: { id, label: name, type, known, color: colorFor(name.toLowerCase()) } });
    elements.push({ data: { source: data.center, target: id } });
  };

  (data.groups      || []).forEach(g => add(g, 'group',  true));
  (data.groups_unk  || []).forEach(g => add(g, 'group',  false));
  (data.forums      || []).forEach(f => add(f, 'market', true));
  (data.forums_unk  || []).forEach(f => add(f, 'market', false));
  (data.peers       || []).forEach(p => add(p, 'actor',  true));
  (data.peers_unk   || []).forEach(p => add(p, 'actor',  false));

  const isDark = document.documentElement.classList.contains('dark');
  const textColor = isDark ? '#e5e7eb' : '#1f2937';
  const edgeColor = isDark ? '#2d333b' : '#d1d5db';
  const centerColor = colorFor(data.center.toLowerCase());

  const cy = cytoscape({
    container,
    elements,
    style: [
      {
        selector: 'node[type="actor-self"]',
        style: {
          'background-color': centerColor,
          'label': 'data(label)',
          'color': textColor,
          'text-valign': 'bottom',
          'text-margin-y': 8,
          'font-size': 14,
          'font-weight': 700,
          'width': 48,
          'height': 48,
          'border-width': 3,
          'border-color': '#fff',
          'text-outline-width': 2,
          'text-outline-color': isDark ? '#0f1117' : '#f8f9fa',
        }
      },
      {
        selector: 'node[type="group"]',
        style: {
          'background-color': 'data(color)',
          'shape': 'round-rectangle',
          'label': 'data(label)',
          'color': textColor,
          'text-valign': 'bottom',
          'text-margin-y': 6,
          'font-size': 12,
          'width': 36,
          'height': 36,
          'text-outline-width': 2,
          'text-outline-color': isDark ? '#0f1117' : '#f8f9fa',
        }
      },
      {
        selector: 'node[type="market"]',
        style: {
          'background-color': 'data(color)',
          'shape': 'diamond',
          'label': 'data(label)',
          'color': textColor,
          'text-valign': 'bottom',
          'text-margin-y': 6,
          'font-size': 12,
          'width': 34,
          'height': 34,
          'text-outline-width': 2,
          'text-outline-color': isDark ? '#0f1117' : '#f8f9fa',
        }
      },
      {
        selector: 'node[type="actor"]',
        style: {
          'background-color': 'data(color)',
          'shape': 'ellipse',
          'label': 'data(label)',
          'color': textColor,
          'text-valign': 'bottom',
          'text-margin-y': 6,
          'font-size': 12,
          'width': 32,
          'height': 32,
          'text-outline-width': 2,
          'text-outline-color': isDark ? '#0f1117' : '#f8f9fa',
        }
      },
      {
        selector: 'node[?known]',
        style: { 'cursor': 'pointer' }
      },
      {
        selector: 'node[!known][type!="actor-self"]',
        style: { 'opacity': 0.55 }
      },
      {
        selector: 'edge',
        style: {
          'width': 2,
          'line-color': edgeColor,
          'curve-style': 'bezier',
          'target-arrow-color': edgeColor,
          'target-arrow-shape': 'triangle',
          'arrow-scale': 0.8,
        }
      },
    ],
    layout: {
      name: 'cose',
      animate: true,
      animationDuration: 400,
      nodeRepulsion: () => 6000,
      nodeOverlap: 30,
      idealEdgeLength: () => 120,
      gravity: 0.5,
      padding: 40,
    },
    userZoomingEnabled: true,
    userPanningEnabled: true,
    boxSelectionEnabled: false,
  });

  // Click → navigate to entity page
  cy.on('tap', 'node[?known]', (e) => {
    const n = e.target;
    const type = n.data('type');
    const label = n.data('label');
    if (type === 'group')       location.href = '/group/'  + encodeURIComponent(label);
    else if (type === 'market') location.href = '/market/' + encodeURIComponent(label);
    else if (type === 'actor')  location.href = '/actor/'  + encodeURIComponent(label);
  });
});
