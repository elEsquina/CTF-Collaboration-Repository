import {useState} from 'react';
import {Box, FileArchive, Eye, EyeOff, LoaderCircle, AlertCircle} from 'lucide-react';
import {categoryName} from '../services/api';
export function Badge({category, docker}) { return category ? <span className={`badge category-${category}`}>{categoryName(category)}</span> : <span className="badge deployment">{docker ? <Box size={13}/> : <FileArchive size={13}/>} {docker ? 'Docker' : 'Static'}</span>; }
export function Loading() {return <div className="state"><LoaderCircle className="animate-spin" size={24}/> Loading repository…</div>;}
export function ErrorMessage({message}) {return message ? <div className="error" role="alert"><AlertCircle size={18}/><span>{message}</span></div> : null;}
export function SecretInput({value, onChange, id='flag', required=true}) {
 const [visible,setVisible] = useState(false);
 return <div className="secret-input"><input id={id} type={visible?'text':'password'} value={value} onChange={onChange} required={required} maxLength={4096} autoComplete="off"/><button type="button" className="icon-button" aria-label={visible?'Hide flag':'Show flag'} onClick={()=>setVisible(!visible)}>{visible?<EyeOff size={18}/>:<Eye size={18}/>}</button></div>;
}
