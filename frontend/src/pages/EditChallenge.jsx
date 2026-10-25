import ChallengeForm from '../components/ChallengeForm';
import {ErrorMessage,Loading} from '../components/UI';
import useChallenge from '../services/useChallenge';
export default function EditChallenge() {const {challenge,error}=useChallenge();return error?<ErrorMessage message={error}/>:challenge?<ChallengeForm key={challenge.id} challenge={challenge}/>:<Loading/>;}
