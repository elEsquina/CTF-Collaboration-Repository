import {useState} from 'react';
import {Link, useNavigate} from 'react-router-dom';
import {ArrowLeft, UploadCloud, FileArchive, Save, LoaderCircle, Info} from 'lucide-react';
import {api, categories} from '../services/api';
import {ErrorMessage, SecretInput} from './UI';
export default function ChallengeForm({challenge}) {
 const editing = Boolean(challenge), navigate = useNavigate();
 const [fields,setFields] = useState(challenge ? {name:challenge.name,description:challenge.description,flag:challenge.flag,category:challenge.category,requires_docker:challenge.requires_docker} : {name:'',description:'',flag:'',category:'web',requires_docker:false});
 const [archive,setArchive] = useState(null), [error,setError] = useState(''), [busy,setBusy] = useState(false);
 const change = key => event => { const value = event.target.value; setFields(current => ({...current,[key]:value})); };
 async function submit(event) {
  event.preventDefault(); setError('');
  if (['name','description','flag'].some(key=>!fields[key].trim())) return setError('Name, description, and flag cannot be blank.');
  if (!editing && !archive) return setError('Choose a challenge ZIP archive.');
  if (archive && !archive.name.toLowerCase().endsWith('.zip')) return setError('Choose a .zip file.');
  setBusy(true);
  try {
   let result;
   if (editing && !archive) result = await api(`/challenges/${challenge.id}`, {method:'PATCH',body:JSON.stringify(fields)});
   else {
    const data = new FormData(); data.append('archive',archive);
    if (editing) data.append('metadata',JSON.stringify(fields));
    else Object.entries(fields).forEach(([key,value])=>data.append(key,value));
    result = await api(editing?`/challenges/${challenge.id}/archive`:'/challenges',{method:editing?'PUT':'POST',body:data});
   }
   navigate(`/challenges/${result.data.id}`, {state:{success:editing?'Challenge updated successfully.':'Challenge added to the repository.'}});
  } catch(e) {setError(e.message);} finally {setBusy(false);}
 }
 return <div className="form-page"><Link className="back" to={editing?`/challenges/${challenge.id}`:'/'}><ArrowLeft size={16}/> {editing?'Back to challenge':'Back to repository'}</Link><h1>{editing?'Edit challenge':'Submit a challenge'}</h1>
 <form className="panel challenge-form" onSubmit={submit}><ErrorMessage message={error}/><fieldset disabled={busy}><div className="section-title"><span>01</span><h2>Challenge details</h2></div>
 <label htmlFor="name">Challenge name <span>*</span></label><input id="name" placeholder="e.g. A matter of trust" value={fields.name} onChange={change('name')} maxLength={200} required/>
 <label htmlFor="description">Description <span>*</span><small>Markdown supported</small></label><textarea id="description" rows={7} placeholder="Describe the challenge, its context, and any setup instructions…" value={fields.description} onChange={change('description')} maxLength={100000} required/>
 <label htmlFor="flag">Challenge flag <span>*</span></label><SecretInput value={fields.flag} onChange={change('flag')}/>
 <div className="form-columns"><div><label htmlFor="category">Category <span>*</span></label><select id="category" value={fields.category} onChange={change('category')}>{categories.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></div><div><label id="docker-label">Requires Docker? <span>*</span></label><div className="segmented" role="group" aria-labelledby="docker-label">{[false,true].map(value=><button type="button" key={String(value)} className={fields.requires_docker===value?'selected':''} aria-pressed={fields.requires_docker===value} onClick={()=>setFields(current=>({...current,requires_docker:value}))}>{value?'Yes, Docker':'No, static'}</button>)}</div></div></div>
 <div className="section-title second"><span>02</span><h2>Challenge files</h2></div><div className="info"><Info size={18}/><p>{fields.requires_docker?'Include a Dockerfile or Compose file and a dist/ directory at the root, or inside one enclosing folder.':'No required folder structure.'}</p></div>
 <label className="upload" htmlFor="archive"><UploadCloud size={30}/><strong>{archive?archive.name:editing?'Choose a replacement ZIP':'Choose your challenge ZIP'}</strong><span>{archive?`${(archive.size/1024/1024).toFixed(2)} MB`:'Click to browse · ZIP archives only'}</span><input id="archive" type="file" accept=".zip,application/zip" onChange={e=>setArchive(e.target.files[0]||null)} required={!editing}/></label>
 {editing && <p className="hint"><FileArchive size={14}/> Current: {challenge.original_filename}. Leave empty to keep it.</p>}
 <div className="form-footer"><Link className="button secondary" to={editing?`/challenges/${challenge.id}`:'/'}>Cancel</Link><button className="button primary" disabled={busy}>{busy?<LoaderCircle size={17} className="animate-spin"/>:<Save size={17}/>} {busy?'Validating and saving…':editing?'Save changes':'Submit challenge'}</button></div></fieldset></form></div>;
}
