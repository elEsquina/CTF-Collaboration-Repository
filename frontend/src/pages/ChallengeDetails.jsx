import {useState} from 'react';
import {Link,useLocation} from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import {ArrowLeft,Download,Pencil,Eye,EyeOff,Flag,CalendarDays,FileArchive,CheckCircle2} from 'lucide-react';
import {Badge,ErrorMessage,Loading} from '../components/UI';
import {date} from '../services/api';
import useChallenge from '../services/useChallenge';
export default function ChallengeDetails() {
 const {challenge:c,error}=useChallenge(),[visible,setVisible]=useState(false),location=useLocation();
 if(error)return <ErrorMessage message={error}/>;if(!c)return <Loading/>;
 return <><Link className="back" to="/"><ArrowLeft size={16}/>Back to repository</Link>{location.state?.success&&<div className="success" role="status"><CheckCircle2 size={18}/>{location.state.success}</div>}<div className="page-heading detail-heading"><div><div className="badges"><Badge category={c.category}/><Badge docker={c.requires_docker}/></div><h1>{c.name}</h1><p className="subtitle">Challenge #{String(c.id).padStart(3,'0')}</p></div><Link className="button secondary" to={`/challenges/${c.id}/edit`}><Pencil size={16}/>Edit challenge</Link></div><div className="detail-grid"><article className="panel description-panel"><div className="markdown"><ReactMarkdown skipHtml components={{img:({alt})=><span>[Image: {alt}]</span>,a:({children,href})=><a href={href} target="_blank" rel="noreferrer noopener">{children}</a>}}>{c.description}</ReactMarkdown></div></article><aside><div className="panel detail-panel"><h2><FileArchive size={18}/>Challenge archive</h2><p className="filename">{c.original_filename}</p><a className="button primary full" href={`/api/challenges/${c.id}/download`}><Download size={17}/>Download ZIP</a></div><div className="panel detail-panel"><h2><Flag size={18}/>Challenge flag</h2><div className="flag-display"><code>{visible?c.flag:'••••••••••••••••'}</code><button className="icon-button" aria-label={visible?'Hide flag':'Show flag'} onClick={()=>setVisible(!visible)}>{visible?<EyeOff size={18}/>:<Eye size={18}/>}</button></div></div><div className="panel detail-panel"><h2><CalendarDays size={18}/>Archive history</h2><dl><dt>Created</dt><dd>{date(c.created_at)}</dd><dt>Last updated</dt><dd>{date(c.updated_at)}</dd></dl></div></aside></div></>;
}
