import {useEffect,useState} from 'react';
import {useParams} from 'react-router-dom';
import {api} from './api';
export default function useChallenge() {
 const {id}=useParams(),[challenge,setChallenge]=useState(null),[error,setError]=useState('');
 useEffect(()=>{let active=true;setChallenge(null);setError('');api(`/challenges/${id}`).then(({data})=>{if(active)setChallenge(data);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[id]);
 return {challenge,error};
}
