import React, { useState } from 'react';
import {
  LibraryIcon,
  SearchIcon,
  BookIcon,
  CopyIcon,
  CheckIcon,
  SparklesIcon,
  ScaleIcon,
  ChevronRightIcon,
  ExternalLinkIcon
} from './Icons';

const STATUTES_DATABASE = [
  {
    id: 'it_act',
    name: 'Information Technology Act, 2000',
    shortName: 'IT Act 2000',
    category: 'Cyber Law',
    enacted: '2000',
    jurisdiction: 'India',
    sectionsCount: 94,
    description: 'Primary Indian law dealing with cybercrime, electronic commerce, digital signatures, and electronic records.',
    sections: [
      {
        section: '43',
        title: 'Penalty and compensation for damage to computer, computer system, etc.',
        text: 'If any person without permission of the owner or any other person who is incharge of a computer, computer system or computer network: (a) accesses or secures access to such computer, computer system or computer network; (b) downloads, copies or extracts any data, computer data base or information from such computer... he shall be liable to pay damages by way of compensation to the person so affected.',
        penalty: 'Civil liability: Compensation up to ₹1 Crore to affected parties.',
      },
      {
        section: '66',
        title: 'Computer related offences',
        text: 'If any person, dishonestly or fraudulently, does any act referred to in section 43, he shall be punishable with imprisonment for a term which may extend to three years or with fine which may extend to five lakh rupees or with both.',
        penalty: 'Criminal penalty: Up to 3 years imprisonment or fine up to ₹5,00,000 or both.',
      },
      {
        section: '66B',
        title: 'Punishment for dishonestly receiving stolen computer resource or communication device',
        text: 'Whoever dishonestly receives or retains any stolen computer resource or communication device knowing or having reason to believe the same to be stolen computer resource or communication device, shall be punished with imprisonment of either description for a term which may extend to three years or with fine which may extend to one lakh rupees or with both.',
        penalty: 'Up to 3 years imprisonment or fine up to ₹1,00,000.',
      },
      {
        section: '72A',
        title: 'Punishment for disclosure of information in breach of lawful contract',
        text: 'Save as otherwise provided in this Act or any other law for the time being in force, any person including an intermediary who, while providing services under the terms of lawful contract, has secured access to any material containing personal information about another person, with the intent to cause or knowing that he is likely to cause wrongful loss or wrongful gain discloses, without the consent of the person concerned, shall be punished.',
        penalty: 'Imprisonment up to 3 years, or fine up to ₹5,00,000, or both.',
      }
    ]
  },
  {
    id: 'companies_act',
    name: 'Companies Act, 2013',
    shortName: 'Companies Act 2013',
    category: 'Corporate Law',
    enacted: '2013',
    jurisdiction: 'India',
    sectionsCount: 470,
    description: 'Statute regulating the incorporation of a company, responsibilities of a company, directors, dissolution of a company.',
    sections: [
      {
        section: '134',
        title: 'Financial statement, Board’s report, etc.',
        text: 'The financial statement, including consolidated financial statement, if any, shall be approved by the Board of Directors before they are signed on behalf of the Board... The Board Report shall include the state of the company affairs, details in respect of frauds reported by auditors, and directors responsibility statement.',
        penalty: 'Company liable to fine of ₹3 Lakhs; every officer in default liable to ₹50,000.',
      },
      {
        section: '166',
        title: 'Duties of directors',
        text: 'A director of a company shall act in accordance with the articles of the company. A director shall act in good faith in order to promote the objects of the company for the benefit of its members as a whole, and in the best interests of the company, its employees, the shareholders, the community and for the protection of environment.',
        penalty: 'Fine not less than ₹1,00,000 which may extend to ₹5,00,000.',
      },
      {
        section: '447',
        title: 'Punishment for fraud',
        text: 'Without prejudice to any liability including repayment of any debt under this Act or any other law, any person who is found to be guilty of fraud involving an amount of at least ten lakh rupees or one percent of the turnover of the company, whichever is lower, shall be punishable with imprisonment for a term which shall not be less than six months but which may extend to ten years.',
        penalty: 'Imprisonment from 6 months to 10 years and fine up to 3x the amount involved in fraud.',
      }
    ]
  },
  {
    id: 'bns',
    name: 'Bharatiya Nyaya Sanhita, 2023',
    shortName: 'BNS 2023',
    category: 'Criminal Law',
    enacted: '2023',
    jurisdiction: 'India',
    sectionsCount: 358,
    description: 'The substantive criminal code of India, replacing the Indian Penal Code 1860 with modernised provisions.',
    sections: [
      {
        section: '318',
        title: 'Cheating (Replaced IPC Section 415 & 420)',
        text: 'Whoever, by deceiving any person, fraudulently or dishonestly induces the person so deceived to deliver any property to any person, or to consent that any person shall retain any property, or intentionally induces the person so deceived to do or omit to do anything which he would not do or omit if he were not so deceived, is said to "cheat".',
        penalty: 'Imprisonment up to 7 years and liability to fine.',
      },
      {
        section: '336',
        title: 'Forgery (Replaced IPC Section 463)',
        text: 'Whoever makes any false documents or false electronic record or part of a document or electronic record, with intent to cause damage or injury, to the public or to any person, or to support any claim or title, commits forgery.',
        penalty: 'Imprisonment up to 2 years, or fine, or both.',
      }
    ]
  },
  {
    id: 'contract_act',
    name: 'Indian Contract Act, 1872',
    shortName: 'Contract Act 1872',
    category: 'Commercial Law',
    enacted: '1872',
    jurisdiction: 'India',
    sectionsCount: 238,
    description: 'Fundamental law governing formation, validity, breach, indemnity, and enforcement of agreements and contracts.',
    sections: [
      {
        section: '73',
        title: 'Compensation for loss or damage caused by breach of contract',
        text: 'When a contract has been broken, the party who suffers by such breach is entitled to receive, from the party who has broken the contract, compensation for any loss or damage caused to him thereby, which naturally arose in the usual course of things from such breach.',
        penalty: 'Civil damages & indemnification.',
      },
      {
        section: '74',
        title: 'Compensation for breach of contract where penalty stipulated for',
        text: 'When a contract has been broken, if a sum is named in the contract as the amount to be paid in case of such breach, the party complaining of the breach is entitled, whether or not actual damage or loss is proved to have been caused thereby, to receive reasonable compensation not exceeding the amount so named.',
        penalty: 'Liquidated damages up to the agreed stipulated ceiling.',
      }
    ]
  }
];

export default function StatuteLibraryView({ onAskCopilot }) {
  const [selectedStatute, setSelectedStatute] = useState(STATUTES_DATABASE[0]);
  const [selectedSection, setSelectedSection] = useState(STATUTES_DATABASE[0].sections[1]); // Section 66
  const [searchFilter, setSearchFilter] = useState('');
  const [copiedId, setCopiedId] = useState(null);
  const [categoryFilter, setCategoryFilter] = useState('All');

  const categories = ['All', 'Cyber Law', 'Corporate Law', 'Criminal Law', 'Commercial Law'];

  const filteredStatutes = STATUTES_DATABASE.filter((statute) => {
    const matchesCat = categoryFilter === 'All' || statute.category === categoryFilter;
    const matchesSearch = !searchFilter.trim() ||
      statute.name.toLowerCase().includes(searchFilter.toLowerCase()) ||
      statute.sections.some((s) =>
        s.section.toLowerCase().includes(searchFilter.toLowerCase()) ||
        s.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
        s.text.toLowerCase().includes(searchFilter.toLowerCase())
      );
    return matchesCat && matchesSearch;
  });

  const handleCopyCitation = (secText, secId) => {
    const citation = `${selectedStatute.name}, Section ${selectedSection.section} - "${selectedSection.title}"`;
    navigator.clipboard.writeText(citation);
    setCopiedId(secId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div
      style={{
        display: 'flex',
        width: '100%',
        height: '100%',
        background: 'var(--bg-app)',
        overflow: 'hidden',
      }}
      className="view-container"
    >
      {/* Left Statutes Catalog Sidebar */}
      <div
        style={{
          width: '320px',
          height: '100%',
          background: 'var(--bg-sidebar)',
          borderRight: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          boxSizing: 'border-box',
        }}
      >
        <div style={{ padding: '20px', borderBottom: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
            <LibraryIcon size={20} color="var(--accent-cyan)" />
            <h2 style={{ fontFamily: 'var(--font-title)', fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Statute Library
            </h2>
          </div>

          {/* Search Box */}
          <div
            style={{
              background: 'var(--bg-input)',
              border: '1px solid var(--border-medium)',
              borderRadius: '8px',
              padding: '6px 12px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <SearchIcon size={14} color="var(--text-muted)" />
            <input
              type="text"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              placeholder="Search statutes & sections..."
              style={{
                width: '100%',
                background: 'transparent',
                border: 'none',
                outline: 'none',
                color: 'var(--text-primary)',
                fontSize: '0.82rem',
              }}
            />
          </div>

          {/* Category Chips */}
          <div style={{ display: 'flex', gap: '4px', marginTop: '12px', flexWrap: 'wrap' }}>
            {categories.map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => setCategoryFilter(cat)}
                style={{
                  background: categoryFilter === cat ? 'rgba(0, 210, 180, 0.15)' : 'var(--bg-card)',
                  border: `1px solid ${categoryFilter === cat ? 'var(--accent-cyan)' : 'var(--border-subtle)'}`,
                  color: categoryFilter === cat ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                  borderRadius: '12px',
                  padding: '3px 8px',
                  fontSize: '0.7rem',
                  fontWeight: 600,
                }}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Statutes List */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {filteredStatutes.map((statute) => {
              const isSelected = selectedStatute.id === statute.id;
              return (
                <div
                  key={statute.id}
                  onClick={() => {
                    setSelectedStatute(statute);
                    setSelectedSection(statute.sections[0] || null);
                  }}
                  style={{
                    background: isSelected ? 'var(--bg-card-hover)' : 'var(--bg-card)',
                    border: `1px solid ${isSelected ? 'var(--accent-blue)' : 'var(--border-subtle)'}`,
                    borderRadius: '8px',
                    padding: '12px',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <span style={{ fontSize: '0.86rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {statute.shortName}
                    </span>
                    <span style={{ fontSize: '0.68rem', color: 'var(--accent-cyan)', background: 'rgba(0, 210, 180, 0.1)', padding: '1px 6px', borderRadius: '4px' }}>
                      {statute.category}
                    </span>
                  </div>
                  <p style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', lineHeight: '1.4', marginBottom: '6px' }}>
                    {statute.description.substring(0, 75)}...
                  </p>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    {statute.sectionsCount} Sections • Enacted {statute.enacted}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Center Section Navigator */}
      <div
        style={{
          width: '280px',
          height: '100%',
          background: 'var(--bg-app)',
          borderRight: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div style={{ padding: '18px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
            Available Sections
          </div>
          <div style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            {selectedStatute.shortName}
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '10px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {selectedStatute.sections.map((sec) => {
              const isSecSelected = selectedSection && selectedSection.section === sec.section;
              return (
                <div
                  key={sec.section}
                  onClick={() => setSelectedSection(sec)}
                  style={{
                    background: isSecSelected ? 'rgba(56, 189, 248, 0.12)' : 'transparent',
                    border: `1px solid ${isSecSelected ? 'rgba(56, 189, 248, 0.3)' : 'transparent'}`,
                    borderRadius: '6px',
                    padding: '10px 12px',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <div style={{ fontSize: '0.82rem', fontWeight: 700, color: isSecSelected ? 'var(--accent-blue)' : 'var(--text-primary)' }}>
                    Section {sec.section}
                  </div>
                  <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', marginTop: '2px', lineHeight: '1.3' }}>
                    {sec.title}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Main Section Reader Pane */}
      <div style={{ flex: 1, height: '100%', overflowY: 'auto', padding: '36px 48px', boxSizing: 'border-box' }}>
        {selectedSection ? (
          <div style={{ maxWidth: '800px', margin: '0 auto' }}>
            {/* Breadcrumb / Category Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '12px' }}>
              <span>{selectedStatute.jurisdiction}</span>
              <span>/</span>
              <span>{selectedStatute.name}</span>
              <span>/</span>
              <span style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>Section {selectedSection.section}</span>
            </div>

            <h1 style={{ fontFamily: 'var(--font-title)', fontSize: '1.8rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '8px' }}>
              Section {selectedSection.section}: {selectedSection.title}
            </h1>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '28px' }}>
              <button
                type="button"
                onClick={() => handleCopyCitation(selectedSection.text, selectedSection.section)}
                style={{
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-medium)',
                  borderRadius: '6px',
                  padding: '6px 12px',
                  color: copiedId === selectedSection.section ? 'var(--defense-pass)' : 'var(--text-secondary)',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                {copiedId === selectedSection.section ? <CheckIcon size={14} color="var(--defense-pass)" /> : <CopyIcon size={14} />}
                <span>{copiedId === selectedSection.section ? 'Citation Copied!' : 'Copy Citation'}</span>
              </button>

              {onAskCopilot && (
                <button
                  type="button"
                  onClick={() => onAskCopilot(`Explain Section ${selectedSection.section} of ${selectedStatute.name} ("${selectedSection.title}") and how it is applied in recent judicial rulings.`)}
                  style={{
                    background: 'rgba(99, 102, 241, 0.15)',
                    border: '1px solid rgba(99, 102, 241, 0.4)',
                    borderRadius: '6px',
                    padding: '6px 12px',
                    color: 'var(--accent-indigo)',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  <SparklesIcon size={14} color="var(--accent-indigo)" />
                  <span>Research with AI Copilot</span>
                </button>
              )}
            </div>

            {/* Official Statutory Text Card */}
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '12px', padding: '24px', marginBottom: '24px', boxShadow: 'var(--shadow-sm)' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--accent-blue)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '14px' }}>
                Official Statutory Provision
              </div>
              <p style={{ fontSize: '1.02rem', lineHeight: '1.8', color: 'var(--text-primary)', whiteSpace: 'pre-line' }}>
                "{selectedSection.text}"
              </p>
            </div>

            {/* Penalties / Legal Liabilities */}
            {selectedSection.penalty && (
              <div style={{ background: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.25)', borderRadius: '10px', padding: '16px 20px', marginBottom: '24px' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f59e0b', textTransform: 'uppercase', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <ScaleIcon size={14} color="#f59e0b" />
                  <span>Statutory Penalties & Consequences</span>
                </div>
                <p style={{ fontSize: '0.9rem', color: '#f8fafc', lineHeight: '1.5' }}>
                  {selectedSection.penalty}
                </p>
              </div>
            )}
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
            Select a statutory section from the sidebar to read its provisions.
          </div>
        )}
      </div>
    </div>
  );
}
